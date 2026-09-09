# RF AI Suite Skills Catalog (SKILLS.md)

This document serves as the operational reference manual for the specialized skills possessed by the **Autonomous RF Hardware Engineer Agent**.

---

## Skill 1: RF Requirements Engineering & CPWG Transmission Line Synthesis

### 1.1 Grounded Coplanar Waveguide (CPWG) Physics
When top copper ground pour is present with gap $s$, the RF signal line is a **Grounded Coplanar Waveguide (CPWG)**, backed by a continuous bottom ground plane.
The characteristic impedance $Z_0$ is computed via conformal mapping:
$$Z_0 = \frac{60\pi}{\sqrt{\varepsilon_{eff}}} \left[ \frac{K(k)}{K(k')} + \frac{K(k_1)}{K(k_1')} \right]^{-1}$$

Where:
$$k = \frac{w}{w + 2s}, \quad k' = \sqrt{1 - k^2}$$
$$k_1 = \frac{\tanh(\pi w / 4h)}{\tanh(\pi (w + 2s) / 4h)}, \quad k_1' = \sqrt{1 - k_1^2}$$
$$\varepsilon_{eff} = 1 + \frac{\varepsilon_r - 1}{2} \frac{K(k')K(k_1)}{K(k)K(k_1')}$$
$$\text{Propagation Delay } t_{pd} = \frac{\sqrt{\varepsilon_{eff}}}{c_0}, \quad v_p = \frac{c_0}{\sqrt{\varepsilon_{eff}}}$$

**Standard FR4 Values ($h = 1.60\text{ mm}, \varepsilon_r = 4.40, s = 0.40\text{ mm}$):**
* $w = \mathbf{1.87\text{ mm}}$ for $Z_0 = 50.0\,\Omega$
* $\varepsilon_{eff} = \mathbf{2.88}$
* $v_p = 1.767 \times 10^8\text{ m/s}$, $t_{pd} = 5.66\text{ ps/mm}$

### 1.2 Closed-Form Passive Circuit Synthesis
* **Symmetric Pi-Attenuators**:
  $$K = 10^{\text{Atten}_{\text{dB}} / 20}$$
  $$R_{\text{shunt}} = Z_0 \frac{K + 1}{K - 1}, \quad R_{\text{series}} = Z_0 \frac{K^2 - 1}{2K}$$
* **Series LC Tank Bandpass Filters**:
  $$f_0 = \frac{1}{2\pi \sqrt{L C}} \implies C = \frac{1}{(2\pi f_0)^2 L}$$
* **Butterworth 3-Pole Low-Pass Filters**:
  $$C_1 = C_2 = \frac{1}{2\pi f_c Z_0}, \quad L_1 = \frac{2 Z_0}{2\pi f_c}$$
* **Wideband RF Bias Tees**:
  $$X_L = 2\pi f_0 L \gg Z_0 \quad (L = 100\text{ nH}), \quad X_C = \frac{1}{2\pi f_0 C} \ll Z_0 \quad (C = 100\text{ pF})$$

---

## Skill 2: Programmatic KiCad 10 Schematic Generation & Rasterization

### 2.1 KiCad 10 S-Expression Generation
* Generates valid `(kicad_sch ...)` syntax conforming to KiCad 10 format.
* Symbols used: `Device:R`, `Device:C`, `Device:L`, `Connector:Conn_Coaxial`, `power:GND`.
* Assigns standard 0805 SMD footprints (`Resistor_SMD:R_0805_2012Metric`, `Capacitor_SMD:C_0805_2012Metric`, `Inductor_SMD:L_0805_2012Metric`) and SMA vertical connectors (`Connector_Coaxial:SMA_Amphenol_132134_Vertical`).

### 2.2 Zoomed High-DPI Vector/Raster Rendering
1. Vector export: `kicad-cli sch export svg --exclude-drawing-sheet --no-background-color -o <dir> <sch>`
2. 300 DPI rasterization using CairoSVG (`cairosvg.svg2png(..., scale=3.0)`).
3. Tight PIL cropping: Calculates bounding box on alpha channel (`alpha.getbbox()`), adds 60px margin, and composites onto pure white background. Output: `renders/schematic_zoomed.png`.

---

## Skill 3: Controlled Impedance PCB Layout with `pcbnew`

### 3.1 Board Physical Architecture
* Board dimensions: Typically $35\text{ mm} \times 20\text{ mm}$ with $2.0\text{ mm}$ corner fillet chamfers on `Edge.Cuts`.
* Collinear horizontal RF signal path along $y = H/2$.
* Connectors placed at board edges: J1 at $x = 4.5\text{ mm}$, J2 at $x = W - 4.5\text{ mm}$.
* M2 mounting holes placed at corners with $3.0\text{ mm}$ inset.

### 3.2 RF Trace Routing & Pad Transition Tapers
* Main RF trace routed with synthesized CPWG width ($w = 1.87\text{ mm}$) on `F.Cu`.
* **Smooth 45° Taper**: Terminate the $1.87\text{ mm}$ trace $0.7\text{ mm}$ outside the 0805 pad, and transition with an $0.80\text{ mm}$ neck directly to the pad center. This completely prevents pad shorts and eliminates capacitive impedance discontinuity.

### 3.3 Ground Stitching & Via Fencing
* Via specifications: $0.40\text{ mm}$ drill, $0.80\text{ mm}$ pad annular ring.
* Via fencing rows at $y = y_{rf} - 2.8\text{ mm}$ and $y = y_{rf} + 5.0\text{ mm}$ along the entire RF line.
* Direct GND vias placed within $1.2\text{ mm}$ of all connector and shunt component ground pads.
* Perimeter ground stitching every $4\text{ mm}$.

### 3.4 Zone Filling & Headless DRC Validation
* Dual copper pours: Top ground pour on `F.Cu` with local clearance $s = 0.40\text{ mm}$; solid ground plane on `B.Cu`.
* Zone filling and DRC validation are executed headlessly in one atomic step:
  ```bash
  kicad-cli pcb drc --refill-zones --save-board --format json -o <drc.json> <board.kicad_pcb>
  ```
* Ensures **0 DRC violations** and **0 DRC warnings**.

---

## Skill 4: High-Fidelity 3D Raytraced Hardware Rendering

Executes photorealistic raytracing via `kicad-cli pcb render`:
```bash
# Isometric 3D view
kicad-cli pcb render --view iso --perspective --quality 3 --width 1920 --height 1080 -o iso_render.png <board>

# Top Orthogonal view
kicad-cli pcb render --view top --perspective off --quality 2 --width 1600 --height 900 -o top_render.png <board>

# Bottom Orthogonal view
kicad-cli pcb render --view bottom --perspective off --quality 2 --width 1600 --height 900 -o bottom_render.png <board>
```

---

## Skill 5: Mechanical CAD Modeling & STEP Assembly

1. Generates 3D OpenCASCADE STEP model using KiCad's headless STEP exporter:
   ```bash
   kicad-cli pcb export step --subst-models --no-dnp -o cad/<name>.step <board>
   ```
2. Embeds the STEP geometry into a native FreeCAD project (`cad/<name>.FCStd`) using `FreeCADCmd`.

---

## Skill 6: Multi-Port S-Parameter EM Extraction (openEMS)

* Calculates 201-point discrete frequency sweeps across operational band ($f_{\text{min}}$ to $f_{\text{max}}$).
* Formulates complete 2-port scattering parameters ($S_{11}, S_{21}, S_{12}, S_{22}$) taking into account transmission line dispersion, dielectric loss tangent ($\tan\delta = 0.02$), and 0805 component parasitics.
* Exports standard Touchstone `.s2p` file conforming to `# GHz S MA R 50`.
* Validates dataset consistency with `scikit-rf` (`rf.Network(s2p_file)`).

---

## Skill 7: Qucs-S Co-Simulation Netlist & Solver Execution

1. Synthesizes Qucs co-simulation schematic (`simulation/<name>_qucs.sch`) and netlist (`simulation/<name>.net`) with two $50\,\Omega$ power ports (`Pac:P1`, `Pac:P2`) connected to a 2-port linear Touchstone block (`2Port:X1`).
2. Executes headless solver:
   ```bash
   qucsator -i simulation/<name>.net -o simulation/<name>.dat
   ```

---

## Skill 8: Publication-Quality RF Performance Visualization

Generates four high-DPI (300 DPI) Matplotlib engineering plots:
1. **S-Parameter Frequency Response (`charts/sparam_plot.png`)**: Insertion Loss $S_{21}$ and Return Loss $S_{11}$ in dB with specification threshold overlays.
2. **Smith Chart (`charts/smith_chart.png`)**: Polar reflection coefficient trajectory normalized to $50\,\Omega$.
3. **Rollett Stability Factor $K$ (`charts/stability_plot.png`)**: Demonstrates unconditional stability ($K > 1.0$) across full band.
4. **Characteristic Impedance Curve (`charts/impedance_plot.png`)**: Input and output real/imaginary impedance vs frequency.

---

## Skill 9: Comprehensive Performance Documentation & BOM Generation

Compiles `PERFORMANCE_REPORT.md` containing:
* Specification vs Simulated Performance comparison table (with PASS/FAIL flags and margins).
* Physical Substrate & Transmission Line table (FR4, $h$, $\varepsilon_r$, $w$, $s$, $\varepsilon_{eff}$, $v_p$, $t_{pd}$).
* Complete Bill of Materials (BOM) with designator, nominal value, 0805 SMD package, and functional role.
* Embedded high-resolution graphic links (zoomed schematic, 3D renders, performance plots).

---

## Skill 10: Production Gerber & Drill ZIP Packaging

1. Plots 26 Gerber layers using `pcbnew.GERBER_JOBFILE_WRITER`:
   * Copper layers: `F_Cu`, `B_Cu`
   * Solder mask: `F_Mask`, `B_Mask`
   * Silkscreen: `F_Silkscreen`, `B_Silkscreen`
   * Solder paste & adhesive: `F_Paste`, `B_Paste`, `F_Adhesive`, `B_Adhesive`
   * Courtyard & Fabrication: `F_Courtyard`, `B_Courtyard`, `F_Fab`, `B_Fab`
   * Mechanical & Edge Cuts: `Edge_Cuts`, `Margin`, `User_*`
2. Generates Excellon NC drill files (`.drl`).
3. Compresses all fabrication outputs into `gerbers_<name>.zip`.

---

## Skill 11: Parametric Tuning & Design Optimization Loop

* Reads `projects/<name>/spec.json`.
* Evaluates simulated insertion loss $S_{21}$ and return loss $S_{11}$ against target specifications.
* If bandwidth or center frequency deviates, the agent recalculates $L$ or $C$ using closed-form perturbation:
  $$\Delta f_0 \approx -\frac{f_0}{2} \left( \frac{\Delta L}{L} + \frac{\Delta C}{C} \right)$$
* Re-runs downstream stages (`python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages pcb,render,em,qucs,charts,report`) until performance converges.

---

## Skill 12: Human-in-the-Loop Stage Review Protocol & Iteration Gating

After executing each task in the workflow, the agent executes an interactive review gate before continuing:

### Stage Handover Protocol
1. **Direct Inline Chat Image Rendering**: Immediately upon completing any stage with visual deliverables, copy `.png` assets to the conversation artifacts directory and render them directly into the chat response using:
   - **Generative UI Embed**: Self-contained Tailwind card with base64 embedded images: `<agent-embed src="file:///<artifact_path>/review_renders.html"></agent-embed>`.
   - **Markdown Image Embed**: Direct inline syntax `![<Description>](<artifact_path>)`.
   - **No Empty Turns**: Never call `ask_question` in an isolated step without the visual render and deliverables table in the chat body.
2. **Deliverables Summary**: Itemize output files with relative paths, sizes, and engineering parameters.
3. **Engineering Integrity**: Confirm 0 DRC errors, CPWG 50Ω matching, and specification margins.
4. **Interactive Choice (`ask_question`)**:
   - `(Recommended) I am satisfied with the output of this task. Proceed to the next task.`
   - `I'd like to provide suggestions or adjust parameters to reiterate this task.`
   - `Stop the process here so I can review the deliverables and think through next steps.`



### Stage Review Matrix

| Stage | Review Deliverables | Visual Check | Passing Criteria |
|---|---|---|---|
| **1. schematic** | `<name>.kicad_sch`<br>`renders/schematic_zoomed.png` | Zoomed schematic crop | Valid KiCad 10 syntax, correct 0805 symbols, 50Ω ports |
| **2. pcb** | `<name>.kicad_pcb`<br>`<name>_drc.json` | DRC error report | **0 violations, 0 warnings**, CPWG $w=1.87\text{mm}$, $s=0.40\text{mm}$ |
| **3. render** | `renders/iso_render.png`<br>`renders/top_render.png`<br>`renders/bottom_render.png` | 3D Raytraced views | SMA connector clearance, ground stitching, pad solder joints |
| **4. cad** | `cad/<name>.step`<br>`cad/<name>.FCStd` | Mechanical geometry check | Valid STEP solid assembly, edge chamfers, M2 mounting holes |
| **5. em** | `simulation/<name>.s2p`<br>`simulation/<name>_openems.m` | Touchstone file summary | Valid Touchstone format, 201 sweep points, passive S-params |
| **6. qucs** | `simulation/<name>.dat`<br>`simulation/<name>.net` | Simulation convergence log | Qucsator-RF solver zero-error exit, dataset generated |
| **7. charts** | `charts/sparam_plot.png`<br>`charts/smith_chart.png`<br>`charts/stability_plot.png` | 300 DPI Matplotlib charts | Target $S_{21}$ achieved, Return loss $S_{11} < -15\text{ dB}$, $K > 1$ |
| **8. gerbers** | `gerbers_<name>.zip` | Gerber file manifest | 26 production layers, Excellon drill file (.drl) included |
| **9. report** | `PERFORMANCE_REPORT.md` | Final documentation & BOM | Margin analysis table, complete 0805 BOM, graphic links |

