import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, Cloud, Cpu, HardDrive, KeyRound, LayoutDashboard, Monitor, Palette, Play, Power, RefreshCcw, Server, Square, Terminal as TerminalIcon, Trash2, Wifi } from "lucide-react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import "./styles.css";
import { API_URL, OSImage, ResourceSummary, Vps, api, token } from "./lib/api";

function AuthPage({ onLogin }: { onLogin: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      if (mode === "register") {
        await api("/api/auth/register", { method: "POST", body: JSON.stringify({ email, username, password }) });
        setNotice("Account created. You can now log in.");
        setMode("login");
      } else {
        const data = await api<{ access_token: string }>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
        localStorage.setItem("aether-token", data.access_token);
        onLogin();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }
  return <main className="login">
    <section className="login-panel">
      <Cloud size={36} />
      <h1>AetherCloud</h1>
      <p>{mode === "login" ? "Welcome back." : "Create your account."}</p>
      <form onSubmit={submit}>
        <input placeholder="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        {mode === "register" && <input placeholder="Username (min 3 chars)" minLength={3} value={username} onChange={(event) => setUsername(event.target.value)} />}
        <input placeholder="Password (min 12 chars)" type="password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} />
        {error && <span className="error">{error}</span>}
        {notice && <span className="notice">{notice}</span>}
        <button>{mode === "login" ? "Login" : "Register"}</button>
      </form>
      <p className="auth-switch">
        {mode === "login" ? (
          <>No account yet? <button type="button" className="link" onClick={() => setMode("register")}>Create one</button></>
        ) : (
          <>Already have an account? <button type="button" className="link" onClick={() => setMode("login")}>Login</button></>
        )}
      </p>
      {mode === "login" && <small className="demo-hint">Default admin &mdash; admin@aethercloud.local / AetherCloud@12345</small>}
    </section>
  </main>;
}

function DeployWizard({ onCreated }: { onCreated: () => void }) {
  const [images, setImages] = useState<OSImage[]>([]);
  const [resources, setResources] = useState<ResourceSummary | null>(null);
  const [osImageId, setOsImageId] = useState<number>();
  const [cpu, setCpu] = useState(2);
  const [ram, setRam] = useState(4096);
  const [storage, setStorage] = useState(40);
  const [message, setMessage] = useState("");
  useEffect(() => {
    api<OSImage[]>("/api/vps/images").then((data) => { setImages(data); setOsImageId(data[0]?.id); });
    api<ResourceSummary>("/api/vps/resources").then(setResources);
  }, []);
  async function deploy() {
    setMessage("Deploying real LXD VPS...");
    try {
      await api<Vps>("/api/vps", { method: "POST", body: JSON.stringify({ os_image_id: osImageId, cpu_cores: cpu, ram_mb: ram, storage_gb: storage }) });
      setMessage("VPS ready.");
      onCreated();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Deployment failed");
    }
  }
  return <section className="panel deploy">
    <h2>Deploy VPS</h2>
    <div className="wizard-grid">
      <label>Operating System<select value={osImageId} onChange={(event) => setOsImageId(Number(event.target.value))}>{images.map((image) => <option key={image.id} value={image.id}>{image.label}</option>)}</select></label>
      <label>CPU Cores<input type="number" min={1} value={cpu} onChange={(event) => setCpu(Number(event.target.value))} /></label>
      <label>RAM MB<input type="number" min={256} step={256} value={ram} onChange={(event) => setRam(Number(event.target.value))} /></label>
      <label>Storage GB<input type="number" min={5} value={storage} onChange={(event) => setStorage(Number(event.target.value))} /></label>
    </div>
    {resources && <div className="resource-strip">
      <span>Available CPU {resources.available_cpu_cores}/{resources.host_cpu_cores}</span>
      <span>RAM {Math.round(resources.available_ram_mb / 1024)}GB / {Math.round(resources.host_ram_mb / 1024)}GB</span>
      <span>Storage {resources.available_storage_gb}GB / {resources.host_storage_gb}GB</span>
    </div>}
    <button className="primary" onClick={deploy}><Play size={16} /> Deploy VPS</button>
    {message && <p className="muted">{message}</p>}
  </section>;
}

function WebTerminal({ vps }: { vps: Vps }) {
  const ref = React.useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const terminal = new Terminal({ cursorBlink: true, fontSize: 14, theme: { background: "#08111f" } });
    const fit = new FitAddon();
    terminal.loadAddon(fit);
    terminal.open(ref.current);
    fit.fit();
    const url = API_URL.replace(/^http/, "ws") + `/api/vps/${vps.vps_id}/terminal?token=${token()}`;
    const ws = new WebSocket(url);
    terminal.onData((data) => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify({ type: "input", data })));
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "ready") terminal.writeln(`Connected to ${vps.vps_id}`);
      } catch {
        terminal.write(event.data);
      }
    };
    const resize = () => { fit.fit(); ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify({ type: "resize", rows: terminal.rows, cols: terminal.cols })); };
    window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); ws.close(); terminal.dispose(); };
  }, [vps.vps_id]);
  return <div className="terminal" ref={ref} />;
}

function VpsDetails({ vps, refresh }: { vps: Vps; refresh: () => void }) {
  const [tmate, setTmate] = useState<any>(null);
  async function action(path: string, method = "POST") {
    await api(`/api/vps/${vps.vps_id}/${path}`, { method });
    refresh();
  }
  async function generateTmate() {
    setTmate(await api(`/api/vps/${vps.vps_id}/tmate`, { method: "POST" }));
  }
  return <section className="panel details">
    <div className="details-head"><h2>{vps.vps_id}</h2><span className={`status ${vps.status}`}>{vps.status}</span></div>
    <div className="stats-grid">
      <span><Cpu /> {vps.cpu_cores} Cores</span><span><Activity /> {Math.round(vps.ram_mb / 1024)} GB RAM</span><span><HardDrive /> {vps.storage_gb} GB</span><span><Wifi /> {vps.ip_address ?? "IP pending"}</span>
    </div>
    <div className="actions">
      <button onClick={() => action("start")}><Power size={15} /> Start</button>
      <button onClick={() => action("stop")}><Square size={15} /> Stop</button>
      <button onClick={() => action("restart")}><RefreshCcw size={15} /> Restart</button>
      <button onClick={() => action("", "DELETE")}><Trash2 size={15} /> Delete</button>
      <button onClick={() => action("password")}><KeyRound size={15} /> Change Password</button>
      <button onClick={generateTmate}><Monitor size={15} /> Regenerate TMATE</button>
    </div>
    {tmate && <div className="tmate"><strong>TMATE ACCESS</strong><code>{tmate.ssh_session ?? "SSH session unavailable"}</code><code>{tmate.web_session ?? "Web session unavailable"}</code></div>}
    <WebTerminal vps={vps} />
  </section>;
}

function App() {
  const [loggedIn, setLoggedIn] = useState(Boolean(token()));
  const [vps, setVps] = useState<Vps[]>([]);
  const [selected, setSelected] = useState<Vps | null>(null);
  const refresh = () => api<Vps[]>("/api/vps").then((data) => { setVps(data); setSelected((current) => data.find((item) => item.vps_id === current?.vps_id) ?? data[0] ?? null); });
  useEffect(() => { if (loggedIn) refresh(); }, [loggedIn]);
  if (!loggedIn) return <AuthPage onLogin={() => setLoggedIn(true)} />;
  return <div className="app">
    <aside>
      <h1><Cloud /> AetherCloud</h1>
      <button><LayoutDashboard size={17} /> Overview</button>
      <button><Server size={17} /> VPS</button>
      <button><TerminalIcon size={17} /> Terminal Sessions</button>
      <button><Palette size={17} /> Branding</button>
    </aside>
    <main>
      <header><div><h1>VPS Control Panel</h1><p>Local LXD instances, real resource validation, isolated terminal access.</p></div><button onClick={() => { localStorage.removeItem("aether-token"); setLoggedIn(false); }}>Logout</button></header>
      <DeployWizard onCreated={refresh} />
      <section className="vps-list">{vps.map((item) => <button key={item.vps_id} className={selected?.vps_id === item.vps_id ? "selected" : ""} onClick={() => setSelected(item)}><Server size={18} /><span>{item.vps_id}</span><small>{item.status}</small></button>)}</section>
      {selected && <VpsDetails vps={selected} refresh={refresh} />}
    </main>
  </div>;
}

createRoot(document.getElementById("root")!).render(<App />);
