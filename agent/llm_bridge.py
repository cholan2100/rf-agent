"""
LLM Integration & Agent Bridge for RF AI Suite.
Supports:
1. Agent Bridge ('agent' / 'bridge') -> routes requests through Antigravity via filesystem IPC (.bridge/)
2. Google Gemini REST API ('gemini') -> direct REST API with GEMINI_API_KEY
3. OpenAI / Ollama REST API ('openai') -> direct REST API with OPENAI_API_KEY / OPENAI_BASE_URL
4. Anthropic REST API ('anthropic') -> direct REST API with ANTHROPIC_API_KEY
5. Analytical Fallback ('analytical') -> classical closed-form RF synthesis engine
"""

import os
import sys
import json
import time
import uuid
import re
import argparse
import requests
from typing import Dict, Any, Optional, Tuple
from .spec import CircuitSpec, parse_custom_circuit, calc_cpwg_dimensions

SYSTEM_PROMPT_SYNTHESIS = """You are an expert RF/Microwave hardware engineer and PCB design AI.
Your task is to take a user's natural language circuit description, target frequency, and impedance,
and synthesize a complete, physically feasible RF PCB specification.

Return ONLY a valid, raw JSON object (no markdown fences, no explanatory text) with this exact schema:
{
  "name": "short_snake_case_name",
  "title": "Clear Descriptive Title",
  "topology": "attenuator" | "lowpass" | "highpass" | "bandpass" | "bias_tee" | "custom",
  "description": "Comprehensive engineering description of the circuit and design choices",
  "f_min_ghz": float,
  "f_0_ghz": float,
  "f_max_ghz": float,
  "z0_ohm": float,
  "target_s21_db": float,
  "target_s11_db": float,
  "target_s22_db": float,
  "width_mm": float,
  "height_mm": float,
  "components": {
    "REFDES": {
      "type": "resistor" | "capacitor" | "inductor" | "connector",
      "value": "e.g. 50R, 100pF, 10nH, SMA_IN",
      "nominal_val": float (in ohms, farads, or henries),
      "package": "e.g. Resistor_SMD:R_0805_2012Metric, Capacitor_SMD:C_0805_2012Metric",
      "role": "Functional role in circuit"
    }
  },
  "llm_reasoning": "Detailed explanation of component value calculations and RF theory used"
}

Component layout rules:
- For 2-port circuits: Must include J1 (Port 1 SMA connector) and J2 (Port 2 SMA connector).
- Standard packages: SMD 0805 (2012 Metric) for passives.
- Standard 50-ohm system impedance unless user explicitly specifies otherwise.
"""

SYSTEM_PROMPT_TUNING = """You are an expert RF/Microwave simulation and optimization engineer.
Inspect the simulated S-parameter performance (S21, S11, S22, Zin, stability factor K) against target specifications.
Diagnose performance bottlenecks (parasitic capacitance, series inductance, substrate dispersion, mismatch)
and propose tuned component values.

Return ONLY a valid JSON object:
{
  "status": "CONVERGED" | "NEEDS_TUNING",
  "diagnosis": "Technical analysis of simulated performance",
  "tuned_components": {
    "REFDES": {"value": "new_val", "nominal_val": float, "reason": "reason for change"}
  },
  "expected_improvements": "Predicted S-parameter changes"
}
"""

class AgentBridgeProvider:
    """Routes LLM calls to Antigravity (the local AI agent) via filesystem IPC (.bridge/)."""

    def __init__(self, bridge_dir: str = ".bridge", timeout_sec: int = 30):
        self.bridge_dir = bridge_dir
        self.timeout_sec = timeout_sec
        self.req_dir = os.path.join(bridge_dir, "requests")
        self.resp_dir = os.path.join(bridge_dir, "responses")
        os.makedirs(self.req_dir, exist_ok=True)
        os.makedirs(self.resp_dir, exist_ok=True)
        self._cleanup_stale_files()

    def _cleanup_stale_files(self):
        """Clean up requests older than 2 hours."""
        now = time.time()
        for d in [self.req_dir, self.resp_dir]:
            if os.path.exists(d):
                for f in os.listdir(d):
                    fp = os.path.join(d, f)
                    try:
                        if os.path.isfile(fp) and (now - os.path.getmtime(fp)) > 7200:
                            os.remove(fp)
                    except Exception:
                        pass

    def query(self, task_type: str, system_prompt: str, user_prompt: str, context: dict = None) -> Optional[dict]:
        req_id = f"req_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        req_file = os.path.join(self.req_dir, f"{req_id}.json")
        resp_file = os.path.join(self.resp_dir, f"{req_id}.json")

        payload = {
            "id": req_id,
            "timestamp": time.time(),
            "task_type": task_type,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "context": context or {}
        }

        with open(req_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        print("\n" + "═" * 70)
        print(f"⚡ [LLM BRIDGE] Routed query to Agent (Antigravity)")
        print(f"   • Request ID:   {req_id}")
        print(f"   • Task Type:    {task_type}")
        print(f"   • Request File: {req_file}")
        print(f"   • User Prompt:  {user_prompt[:90].strip()}...")
        print(f"   Waiting for Agent response at: {resp_file}")
        print(f"   (Timeout: {self.timeout_sec}s — fallback to analytical engine on timeout)")
        print("═" * 70)

        # Polling loop
        start_t = time.time()
        while time.time() - start_t < self.timeout_sec:
            if os.path.exists(resp_file):
                try:
                    with open(resp_file, "r", encoding="utf-8-sig") as f:
                        data = json.load(f)
                    print(f"✔ [LLM BRIDGE] Received response for {req_id} from Agent!")
                    # Clean up
                    try:
                        os.remove(req_file)
                        os.remove(resp_file)
                    except Exception:
                        pass
                    return data
                except Exception as e:
                    print(f"⚠️ [LLM BRIDGE] Error reading response file: {e}")
            time.sleep(0.5)

        print(f"⏱ [LLM BRIDGE] Timeout ({self.timeout_sec}s) reached without response.")
        return None

    def list_pending_requests(self) -> list[dict]:
        """List all currently pending requests in .bridge/requests/."""
        pending = []
        if os.path.exists(self.req_dir):
            for f in sorted(os.listdir(self.req_dir)):
                if f.endswith(".json"):
                    fp = os.path.join(self.req_dir, f)
                    try:
                        with open(fp, "r", encoding="utf-8-sig") as jf:
                            pending.append(json.load(jf))
                    except Exception:
                        pass
        return pending

    def respond(self, req_id: str, response_data: dict) -> bool:
        """Helper to write response for a pending request."""
        resp_file = os.path.join(self.resp_dir, f"{req_id}.json")
        with open(resp_file, "w", encoding="utf-8") as f:
            json.dump(response_data, f, indent=2)
        return True


class GeminiRESTProvider:
    """Direct Google Gemini REST API client."""

    def __init__(self, api_key: str = None, model: str = "gemini-2.0-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model

    def query(self, system_prompt: str, user_prompt: str) -> Optional[dict]:
        if not self.api_key:
            return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=25)
            r.raise_for_status()
            res = r.json()
            text = res["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception as e:
            print(f"⚠️ [Gemini API] Request failed: {e}")
            return None


class OpenAIRESTProvider:
    """Direct OpenAI or local OpenAI-compatible endpoint (Ollama, vLLM, LM Studio)."""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "no-key")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model

    def query(self, system_prompt: str, user_prompt: str) -> Optional[dict]:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"}
        }
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=25)
            r.raise_for_status()
            res = r.json()
            text = res["choices"][0]["message"]["content"]
            return json.loads(text)
        except Exception as e:
            print(f"⚠️ [OpenAI API] Request failed: {e}")
            return None


class LLMClient:
    """
    Unified LLM router for RF circuit synthesis and simulation tuning.
    Defaults to 'agent' bridge routing through Antigravity.
    """

    def __init__(self, provider: str = "agent", timeout_sec: int = 30):
        self.provider_name = provider.lower()
        self.timeout_sec = timeout_sec

        # Determine active provider
        if self.provider_name in ["agent", "bridge"]:
            self.provider = AgentBridgeProvider(timeout_sec=timeout_sec)
        elif self.provider_name == "gemini":
            self.provider = GeminiRESTProvider()
        elif self.provider_name == "openai":
            self.provider = OpenAIRESTProvider()
        else:
            self.provider = None

    def synthesize_circuit(
        self,
        description: str,
        f0_ghz: float = 1.5,
        z0: float = 50.0,
        substrate_name: str = "FR4",
        er: float = 4.4,
        h_mm: float = 1.6,
        width_mm: float = 30.0,
        height_mm: float = 20.0,
        em_sim_type: str = "traces"
    ) -> CircuitSpec:
        """
        Synthesizes a CircuitSpec using LLM intelligence via the configured provider,
        with graceful fallback to analytical equations if unavailable.
        """
        user_prompt = (
            f"Synthesize an RF circuit for the following user requirement:\n"
            f"Description: '{description}'\n"
            f"Center Frequency f0: {f0_ghz} GHz\n"
            f"System Impedance Z0: {z0} Ohms\n"
            f"Substrate laminate: {substrate_name} (er={er}, thickness h={h_mm} mm)\n"
            f"PCB Dimensions: {width_mm} mm width x {height_mm} mm height\n"
            f"Simulation mode: {em_sim_type}\n"
        )

        context = {
            "description": description,
            "f0_ghz": f0_ghz,
            "z0": z0,
            "substrate_name": substrate_name,
            "er": er,
            "h_mm": h_mm,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "em_sim_type": em_sim_type
        }

        data = None
        if isinstance(self.provider, AgentBridgeProvider):
            data = self.provider.query("circuit_synthesis", SYSTEM_PROMPT_SYNTHESIS, user_prompt, context)
        elif self.provider is not None:
            data = self.provider.query(SYSTEM_PROMPT_SYNTHESIS, user_prompt)

        # Parse LLM response if successfully received
        if data and isinstance(data, dict):
            try:
                spec = self._build_spec_from_dict(data, z0, substrate_name, er, h_mm, width_mm, height_mm, em_sim_type)
                print(f"✔ [LLM Synthesis] Successfully applied AI design: {spec.title}")
                if "llm_reasoning" in data:
                    print(f"   ↳ Rationale: {data['llm_reasoning'][:120]}...")
                return spec
            except Exception as e:
                print(f"⚠️ [LLM Bridge] Parsing LLM response failed: {e}. Using analytical fallback.")

        # Analytical Fallback
        return parse_custom_circuit(
            description=description,
            title=description,
            f0_ghz=f0_ghz,
            z0=z0,
            width_mm=width_mm,
            height_mm=height_mm,
            substrate_name=substrate_name,
            er=er,
            h_mm=h_mm,
            em_sim_type=em_sim_type
        )

    def tune_design_iteration(self, spec: CircuitSpec, sim_data: dict) -> Optional[dict]:
        """Queries LLM for performance analysis and parameter optimization tuning."""
        user_prompt = (
            f"Circuit: {spec.title} (Topology: {spec.topology})\n"
            f"Target S21: {spec.target_s21_db} dB | Simulated S21 mean: {sim_data.get('s21_mean', 0.0):.2f} dB\n"
            f"Target S11: {spec.target_s11_db} dB | Worst S11: {sim_data.get('s11_worst', 0.0):.2f} dB\n"
            f"Stability K min: {sim_data.get('k_min', 1.0):.2f}\n"
            f"Current components:\n" +
            json.dumps({k: v.get("value") for k, v in spec.components.items()}, indent=2)
        )

        if isinstance(self.provider, AgentBridgeProvider):
            return self.provider.query("design_tuning", SYSTEM_PROMPT_TUNING, user_prompt, {"name": spec.name})
        elif self.provider is not None:
            return self.provider.query(SYSTEM_PROMPT_TUNING, user_prompt)
        return None

    def _build_spec_from_dict(
        self,
        d: dict,
        z0: float,
        substrate_name: str,
        er: float,
        h_mm: float,
        width_mm: float,
        height_mm: float,
        em_sim_type: str
    ) -> CircuitSpec:
        """Construct a verified CircuitSpec from LLM synthesis JSON."""
        name = re.sub(r'[^a-zA-Z0-9_]', '_', d.get("name", "custom_circuit").lower()).strip('_')
        title = d.get("title", "AI Synthesized RF Board")
        topology = d.get("topology", "custom")
        desc = d.get("description", "")
        f0 = float(d.get("f_0_ghz", 1.5))
        f_min = float(d.get("f_min_ghz", round(max(0.01, f0 * 0.1), 2)))
        f_max = float(d.get("f_max_ghz", round(f0 * 2.0, 2)))
        target_s21 = float(d.get("target_s21_db", -10.0))
        target_s11 = float(d.get("target_s11_db", -25.0))
        target_s22 = float(d.get("target_s22_db", -25.0))
        comps = d.get("components", {})

        # Ensure J1 and J2 exist
        if "J1" not in comps:
            comps["J1"] = {"type": "connector", "value": "SMA_IN", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": "RF Port 1"}
        if "J2" not in comps:
            comps["J2"] = {"type": "connector", "value": "SMA_OUT", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": "RF Port 2"}

        spec = CircuitSpec(
            name=name,
            title=title,
            topology=topology,
            description=desc,
            f_min_ghz=f_min,
            f_0_ghz=f0,
            f_max_ghz=f_max,
            z0_ohm=z0,
            target_s21_db=target_s21,
            target_s11_db=target_s11,
            target_s22_db=target_s22,
            width_mm=float(d.get("width_mm", width_mm)),
            height_mm=float(d.get("height_mm", height_mm)),
            substrate_name=substrate_name,
            dielectric_er=er,
            substrate_height_mm=h_mm,
            em_sim_type=em_sim_type,
            components=comps
        )
        return spec


# ----------------------------------------------------------------------
# CLI Helper for inspecting or responding to Agent Bridge requests
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="RF AI Suite - LLM Agent Bridge CLI")
    parser.add_argument("--list", action="store_true", help="List pending requests in .bridge/requests/")
    parser.add_argument("--respond", type=str, metavar="REQ_ID", help="Request ID to respond to")
    parser.add_argument("--json", type=str, metavar="JSON_STRING", help="Response JSON string")
    parser.add_argument("--file", type=str, metavar="FILE_PATH", help="Response JSON file path")
    args = parser.parse_args()

    bridge = AgentBridgeProvider()

    if args.list:
        pending = bridge.list_pending_requests()
        print(f"Pending LLM Bridge Requests: {len(pending)}")
        for req in pending:
            print(f"  • ID: {req['id']} | Task: {req['task_type']} | Prompt: {req['user_prompt'][:70]}...")
        return

    if args.respond:
        resp_data = None
        if args.file and os.path.exists(args.file):
            with open(args.file, "r", encoding="utf-8-sig") as f:
                resp_data = json.load(f)
        elif args.json:
            resp_data = json.loads(args.json)
        else:
            print("Error: Specify either --json or --file for response payload.")
            sys.exit(1)

        bridge.respond(args.respond, resp_data)
        print(f"✔ Successfully wrote response for {args.respond}")


if __name__ == "__main__":
    main()
