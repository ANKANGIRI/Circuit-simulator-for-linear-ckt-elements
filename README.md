# Circuit-simulator-for-linear-ckt-elements
A Python-based transient circuit simulator that parses netlists, performs Modified Nodal Analysis (MNA), and visualizes voltage/current waveforms using customizable probes.

# ⚡ Circuit Simulator (GUI + Backend)

A complete **circuit simulation tool** that combines a **graphical circuit designer (frontend)** with a **numerical simulation engine (backend)**.

Build circuits visually, export netlists automatically, and perform **transient analysis** with waveform visualization.

---

## 🚀 Features

### 🎨 Frontend (PyQt6 GUI)
- Drag-and-drop circuit design
- Smart wiring with terminal snapping
- Component rotation and movement
- Editable component values (R, L, C, V, I)
- Voltage and current probes
- Grid-based design canvas
- Multi-threaded simulation (no UI freeze)

### ⚙️ Backend (Simulation Engine)
- Modified Nodal Analysis (MNA)
- Transient simulation using numerical integration
- Supports time-dependent sources (e.g., sin, exp)
- Matrix-based solver using NumPy
- Automatic waveform plotting (Matplotlib)

---

## 🧠 How It Works

1. **Design circuit in GUI**
2. GUI generates:
   - `netlist.txt`
   - `probes.txt`
   - `time.txt`
3. Backend reads these files
4. Solves circuit using MNA:


   
