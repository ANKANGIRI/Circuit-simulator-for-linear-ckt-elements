# import re
# import numpy as np
# import matplotlib.pyplot as plt

# # Uploaded notebook path (for reference / tool use):
# # /mnt/data/ckt_sim.ipynb

# def safe_eval(expr, t):
#     expr = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr)
#     expr = expr.replace('^', '**')
#     allowed = {
#         'sin': np.sin, 'cos': np.cos, 'tan': np.tan,
#         'exp': np.exp, 'sqrt': np.sqrt, 'log': np.log, 'log10': np.log10,
#         'abs': np.abs, 'pi': np.pi, 'e': np.e, 't': t
#     }
#     cleaned = re.sub(r'e[\+\-]?\d+', '', expr)
#     if re.search(r'[^a-zA-Z0-9\s\.\*\/\+\-\(\),_]', cleaned):
#         raise ValueError(f"Invalid characters in expression: {expr}")
#     try:
#         return eval(expr, {"__builtins__": None}, allowed)
#     except Exception:
#         return 0.0


# def parse_netlist(file_name):
#     components = []
#     num_volt_src = 0
#     num_ind = 0
#     max_node = 0

#     try:
#         with open(file_name, 'r') as f:
#             for raw in f:
#                 line = raw.strip().lower()
#                 if not line or line.startswith(('*', '#')):
#                     continue
#                 parts = line.split()
#                 comp_type = parts[0][0]
#                 n1, n2 = int(parts[1]), int(parts[2])
#                 max_node = max(max_node, n1, n2)
#                 if comp_type == 'v':
#                     num_volt_src += 1
#                 elif comp_type == 'l':
#                     num_ind += 1
#                 components.append(parts)
#     except FileNotFoundError:
#         # silent exit on missing netlist
#         return None, None, None, None, None

#     n_nodes = max_node
#     size = n_nodes + num_volt_src + num_ind

#     G = np.zeros((size, size))
#     C = np.zeros((size, size))
#     b_sources = [None] * size

#     vsrc_idx = 0
#     ind_idx = 0

#     for parts in components:
#         ctype = parts[0][0]
#         n1, n2 = int(parts[1]), int(parts[2])
#         val_str = ' '.join(parts[3:])

#         idx1 = n1 - 1 if n1 > 0 else None
#         idx2 = n2 - 1 if n2 > 0 else None

#         def stamp(mat, i, j, value):
#             if i is not None: mat[i, i] += value
#             if j is not None: mat[j, j] += value
#             if i is not None and j is not None:
#                 mat[i, j] -= value
#                 mat[j, i] -= value

#         if ctype == 'r':
#             try:
#                 val = float(val_str)
#                 stamp(G, idx1, idx2, 1.0 / val)
#             except Exception:
#                 pass

#         elif ctype == 'c':
#             try:
#                 val = float(val_str)
#                 stamp(C, idx1, idx2, val)
#             except Exception:
#                 pass

#         elif ctype == 'l':
#             try:
#                 val = float(val_str)
#                 row = n_nodes + num_volt_src + ind_idx
#                 if idx1 is not None:
#                     G[idx1, row] = 1
#                     G[row, idx1] = 1
#                 if idx2 is not None:
#                     G[idx2, row] = -1
#                     G[row, idx2] = -1
#                 G[row, row] = -val
#                 ind_idx += 1
#             except Exception:
#                 pass

#         elif ctype == 'v':
#             row = n_nodes + vsrc_idx
#             b_sources[row] = val_str
#             if idx1 is not None:
#                 G[idx1, row] = 1
#                 G[row, idx1] = 1
#             if idx2 is not None:
#                 G[idx2, row] = -1
#                 G[row, idx2] = -1
#             vsrc_idx += 1

#         elif ctype == 'i':
#             if idx1 is not None:
#                 b_sources[idx1] = (b_sources[idx1] or "") + f"-({val_str})"
#             if idx2 is not None:
#                 b_sources[idx2] = (b_sources[idx2] or "") + f"+({val_str})"

#     return G, C, b_sources, n_nodes, size


# def transient_analysis(G, C, b_sources, size, t_end=0.1, dt=1e-5):
#     if G is None:
#         return None, None
#     t = np.arange(0, t_end, dt)
#     x = np.zeros((size, len(t)))
#     A = C / dt + G
#     try:
#         LHS_factor = np.linalg.inv(A)
#     except np.linalg.LinAlgError:
#         return None, None

#     for i in range(1, len(t)):
#         b = np.zeros(size)
#         for j, expr in enumerate(b_sources):
#             if expr:
#                 try:
#                     b[j] = safe_eval(expr, t[i])
#                 except Exception:
#                     b[j] = 0.0
#         rhs = (C @ x[:, i - 1]) / dt + b
#         x[:, i] = LHS_factor @ rhs

#     return t, x


# def read_probe_file(probe_file):
#     try:
#         with open(probe_file, 'r') as f:
#             for raw in f:
#                 line = raw.strip().lower()
#                 if not line or line.startswith(('*', '#')): 
#                     continue
#                 parts = line.split()
#                 if len(parts) >= 1:
#                     if len(parts) == 1:
#                         return int(parts[0]), 0
#                     else:
#                         return int(parts[0]), int(parts[1])
#     except FileNotFoundError:
#         return None
#     return None


# def read_time_file(time_file):
#     try:
#         with open(time_file, 'r') as f:
#             for raw in f:
#                 line = raw.strip()
#                 if not line or line.startswith(('*', '#')):
#                     continue
#                 parts = line.split()
#                 if len(parts) == 1:
#                     return float(parts[0]), None
#                 elif len(parts) >= 2:
#                     return float(parts[0]), float(parts[1])
#     except FileNotFoundError:
#         return None
#     return None


# def plot_probe_nodes(t, x, n_nodes, probe_pair):
#     nodeP, nodeRef = probe_pair
#     if not (0 <= nodeP <= n_nodes and 0 <= nodeRef <= n_nodes):
#         return
#     vP = x[nodeP - 1, :] if nodeP > 0 else np.zeros(len(t))
#     vR = x[nodeRef - 1, :] if nodeRef > 0 else np.zeros(len(t))
#     vdiff = vP - vR
#     plt.figure(figsize=(10, 6))
#     plt.plot(t, vdiff, label=f"V({nodeP}) - V({nodeRef})")
#     plt.xlabel("Time (s)")
#     plt.ylabel("Voltage (V)")
#     plt.title(f"Probe: Node {nodeP} - Node {nodeRef}")
#     plt.grid(True)
#     plt.legend()
#     plt.show()


# def main():
#     file_name = "netlist.txt"
#     probe_file = "probe.txt"
#     time_file = "time.txt"

#     time_info = read_time_file(time_file)
#     t_end_default = 0.1
#     dt_default = 1e-5

#     if time_info:
#         if time_info[1] is None:
#             t_end = time_info[0]
#             dt = dt_default
#         else:
#             t_end, dt = time_info
#     else:
#         t_end, dt = t_end_default, dt_default

#     G, C, b_src, n_nodes, size = parse_netlist(file_name)
#     if G is None:
#         return

#     t, x = transient_analysis(G, C, b_src, size, t_end=t_end, dt=dt)
#     if t is None:
#         return

#     probe_pair = read_probe_file(probe_file)
#     if probe_pair:
#         plot_probe_nodes(t, x, n_nodes, probe_pair)
#     # else: do nothing and exit silently

# if __name__ == "__main__":
#     main()

import re
import numpy as np
import matplotlib.pyplot as plt

# Uploaded notebook path (for reference / tool use):
# /mnt/data/ckt_sim.ipynb

def safe_eval(expr, t):
    expr = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr)
    expr = expr.replace('^', '**')
    allowed = {
        'sin': np.sin, 'cos': np.cos, 'tan': np.tan,
        'exp': np.exp, 'sqrt': np.sqrt, 'log': np.log, 'log10': np.log10,
        'abs': np.abs, 'pi': np.pi, 'e': np.e, 't': t
    }
    cleaned = re.sub(r'e[\+\-]?\d+', '', expr)
    if re.search(r'[^a-zA-Z0-9\s\.\*\/\+\-\(\),_]', cleaned):
        raise ValueError(f"Invalid characters in expression: {expr}")
    try:
        return eval(expr, {"__builtins__": None}, allowed)
    except Exception:
        return 0.0


def parse_netlist(file_name):
    components = []
    num_volt_src = 0
    num_ind = 0
    max_node = 0

    try:
        with open(file_name, 'r') as f:
            for raw in f:
                line = raw.strip().lower()
                if not line or line.startswith(('*', '#')):
                    continue
                parts = line.split()
                comp_type = parts[0][0]
                n1, n2 = int(parts[1]), int(parts[2])
                max_node = max(max_node, n1, n2)
                if comp_type == 'v':
                    num_volt_src += 1
                elif comp_type == 'l':
                    num_ind += 1
                components.append(parts)
    except FileNotFoundError:
        # silent exit on missing netlist
        return None, None, None, None, None, None

    n_nodes = max_node
    size = n_nodes + num_volt_src + num_ind

    G = np.zeros((size, size))
    C = np.zeros((size, size))
    b_sources = [None] * size

    vsrc_idx = 0
    ind_idx = 0

    # NEW: map voltage source name -> state index in x
    vsrc_map = {}

    for parts in components:
        ctype = parts[0][0]
        name = parts[0].lower()
        n1, n2 = int(parts[1]), int(parts[2])
        val_str = ' '.join(parts[3:])

        idx1 = n1 - 1 if n1 > 0 else None
        idx2 = n2 - 1 if n2 > 0 else None

        def stamp(mat, i, j, value):
            if i is not None:
                mat[i, i] += value
            if j is not None:
                mat[j, j] += value
            if i is not None and j is not None:
                mat[i, j] -= value
                mat[j, i] -= value

        if ctype == 'r':
            try:
                val = float(val_str)
                stamp(G, idx1, idx2, 1.0 / val)
            except Exception:
                pass

        elif ctype == 'c':
            try:
                val = float(val_str)
                stamp(C, idx1, idx2, val)
            except Exception:
                pass

        elif ctype == 'l':
            try:
                val = float(val_str)
                row = n_nodes + num_volt_src + ind_idx
                if idx1 is not None:
                    G[idx1, row] = 1
                    G[row, idx1] = 1
                if idx2 is not None:
                    G[idx2, row] = -1
                    G[row, idx2] = -1
                G[row, row] = -val
                ind_idx += 1
            except Exception:
                pass

        elif ctype == 'v':
            row = n_nodes + vsrc_idx
            # store expression for this source
            b_sources[row] = val_str
            # map name -> row index so we can later read current
            vsrc_map[name] = row

            if idx1 is not None:
                G[idx1, row] = 1
                G[row, idx1] = 1
            if idx2 is not None:
                G[idx2, row] = -1
                G[row, idx2] = -1
            vsrc_idx += 1

        elif ctype == 'i':
            if idx1 is not None:
                b_sources[idx1] = (b_sources[idx1] or "") + f"-({val_str})"
            if idx2 is not None:
                b_sources[idx2] = (b_sources[idx2] or "") + f"+({val_str})"

    return G, C, b_sources, n_nodes, size, vsrc_map


def transient_analysis(G, C, b_sources, size, t_end=0.1, dt=1e-5):
    if G is None:
        return None, None
    t = np.arange(0, t_end, dt)
    x = np.zeros((size, len(t)))
    A = C / dt + G
    try:
        LHS_factor = np.linalg.inv(A)
    except np.linalg.LinAlgError:
        return None, None

    for i in range(1, len(t)):
        b = np.zeros(size)
        for j, expr in enumerate(b_sources):
            if expr:
                try:
                    b[j] = safe_eval(expr, t[i])
                except Exception:
                    b[j] = 0.0
        rhs = (C @ x[:, i - 1]) / dt + b
        x[:, i] = LHS_factor @ rhs

    return t, x


def read_probe_file(probe_file):
    """
    Supports:
      - Voltage probes:  VP1 nodeP nodeRef
      - Current probes:  AP1 VA1
    Also backward-compatible with lines like: 1 0
    Returns a list of probe dicts.
    """
    probes = []
    try:
        with open(probe_file, 'r') as f:
            for raw in f:
                line = raw.strip().lower()
                if not line or line.startswith(('*', '#')):
                    continue
                parts = line.split()
                if not parts:
                    continue

                name = parts[0]  # e.g. vp1, ap1, or maybe a bare node index
                tag = name

                # Voltage probe from frontend: "vp1 nodeP nodeRef"
                if tag.startswith('vp'):
                    if len(parts) == 2:
                        # vp1 nodeP   (assume nodeRef = 0)
                        node_p = int(parts[1])
                        node_ref = 0
                    elif len(parts) >= 3:
                        node_p = int(parts[1])
                        node_ref = int(parts[2])
                    else:
                        continue
                    probes.append({
                        'type': 'voltage',
                        'name': name,
                        'nodeP': node_p,
                        'nodeRef': node_ref
                    })

                # Current probe from frontend: "ap1 va1"
                elif tag.startswith('ap'):
                    if len(parts) >= 2:
                        element = parts[1]  # e.g. "va1"
                        probes.append({
                            'type': 'current',
                            'name': name,
                            'element': element
                        })

                else:
                    # Backward compatibility: treat first integers as nodes
                    nums = []
                    for p in parts:
                        try:
                            nums.append(int(p))
                        except ValueError:
                            pass
                    if nums:
                        node_p = nums[0]
                        node_ref = nums[1] if len(nums) > 1 else 0
                        probes.append({
                            'type': 'voltage',
                            'name': name,
                            'nodeP': node_p,
                            'nodeRef': node_ref
                        })
    except FileNotFoundError:
        return []

    return probes


def read_time_file(time_file):
    try:
        with open(time_file, 'r') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith(('*', '#')):
                    continue
                parts = line.split()
                if len(parts) == 1:
                    return float(parts[0]), None
                elif len(parts) >= 2:
                    return float(parts[0]), float(parts[1])
    except FileNotFoundError:
        return None
    return None


def plot_voltage_probe(t, x, n_nodes, probe):
    nodeP = probe['nodeP']
    nodeRef = probe['nodeRef']
    name = probe.get('name', '')

    if not (0 <= nodeP <= n_nodes and 0 <= nodeRef <= n_nodes):
        return

    vP = x[nodeP - 1, :] if nodeP > 0 else np.zeros(len(t))
    vR = x[nodeRef - 1, :] if nodeRef > 0 else np.zeros(len(t))
    vdiff = vP - vR

    plt.figure(figsize=(10, 6))
    plt.plot(t, vdiff, label=f"V({nodeP}) - V({nodeRef})")
    plt.xlabel("Time (s)")
    plt.ylabel("Voltage (V)")
    title = f"Voltage Probe: {name.upper()}   Node {nodeP} - Node {nodeRef}"
    plt.title(title)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


def plot_current_probe(t, x, vsrc_map, probe):
    """
    Current through an element implemented as a voltage source, e.g. VA1.
    The current is the state variable at the row corresponding to that source.
    """
    elem = probe['element']  # e.g. "va1"
    name = probe.get('name', '')

    row = vsrc_map.get(elem)
    if row is None:
        # no such source found; nothing to plot
        return

    i_wave = x[row, :]

    plt.figure(figsize=(10, 6))
    plt.plot(t, i_wave, label=f"I({elem.upper()})")
    plt.xlabel("Time (s)")
    plt.ylabel("Current (A)")
    title = f"Current Probe: {name.upper()}   I({elem.upper()})"
    plt.title(title)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


def main():
    file_name = "netlist.txt"
    # UPDATED: match frontend output name
    probe_file = "probes.txt"
    time_file = "time.txt"

    time_info = read_time_file(time_file)
    t_end_default = 0.1
    dt_default = 1e-5

    if time_info:
        if time_info[1] is None:
            t_end = time_info[0]
            dt = dt_default
        else:
            t_end, dt = time_info
    else:
        t_end, dt = t_end_default, dt_default

    G, C, b_src, n_nodes, size, vsrc_map = parse_netlist(file_name)
    if G is None:
        return

    t, x = transient_analysis(G, C, b_src, size, t_end=t_end, dt=dt)
    if t is None:
        return

    probes = read_probe_file(probe_file)
    if not probes:
        # no probes -> just exit silently
        return

    # Plot each probe in its own figure
    for pr in probes:
        if pr['type'] == 'voltage':
            plot_voltage_probe(t, x, n_nodes, pr)
        elif pr['type'] == 'current':
            plot_current_probe(t, x, vsrc_map, pr)


if __name__ == "__main__":
    main()

