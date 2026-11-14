import { useEffect, useMemo, useState } from "react";
import { Timelapse } from "./Timelapse";
import { DistanceDial } from "./DistanceDial";
import { imageUrl, loadField, loadIndex } from "../data/loader";
import type { FieldSummary } from "../contract";
import { SimpleViewer } from "../viewer/SimpleViewer";
import { ErrorBoundary } from "../viewer/ErrorBoundary";

type Screen = "home" | "explore" | "timelapse" | "dial" | "compare" | "about";
type IconName =
  | "orbit"
  | "arrow"
  | "search"
  | "spark"
  | "grid"
 
  | "book"
  | "chevron"
  | "filter"
  | "layers"
  | "plus"
  | "minus"
  | "flag"
  | "compare"
  | "export"
  | "play"
  | "pause"
  | "close"
  | "check";

const spaceImage =
  "https://images.unsplash.com/photo-1706800696671-570820e7ff39?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=85&w=1800";

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, React.ReactNode> = {
    arrow: (
      <>
        <path d="M5 12h14M14 7l5 5-5 5" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="6.5" />
        <path d="m16 16 4 4" />
      </>
    ),
    spark: (
      <>
        <path d="M12 3v4M12 17v4M3 12h4M17 12h4" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    grid: (
      <>
        <path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" />
      </>
    ),
    orbit: (
      <>
        <circle cx="12" cy="12" r="2" />
        <ellipse cx="12" cy="12" rx="9" ry="4" transform="rotate(-25 12 12)" />
      </>
    ),
    book: (
      <>
        <path d="M4 5.5A3.5 3.5 0 0 1 7.5 2H11v17H7.5A3.5 3.5 0 0 0 4 22zM20 5.5A3.5 3.5 0 0 0 16.5 2H13v17h3.5a3.5 3.5 0 0 1 3.5 3z" />
      </>
    ),
    chevron: <path d="m9 6 6 6-6 6" />,
    filter: <path d="M4 5h16M7 12h10M10 19h4" />,
    layers: (
      <>
        <path d="m12 3 9 5-9 5-9-5z" />
        <path d="m3 12 9 5 9-5M3 16l9 5 9-5" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    minus: <path d="M5 12h14" />,
    flag: <path d="M5 21V4m0 1h11l-2 4 2 4H5" />,
    compare: (
      <>
        <path d="M8 4v16M16 4v16M5 7l3-3 3 3M13 17l3 3 3-3" />
      </>
    ),
    export: (
      <>
        <path d="M12 3v12m0-12-4 4m4-4 4 4" />
        <path d="M5 13v7h14v-7" />
      </>
    ),
    play: <path d="m9 6 9 6-9 6z" />,
    pause: (
      <>
        <path d="M9 6v12M15 6v12" />
      </>
    ),
    close: <path d="M6 6l12 12M18 6 6 18" />,
    check: <path d="m5 12 4 4L19 6" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

function Logo({ onClick }: { onClick: () => void }) {
  return (
    <button className="logo" onClick={onClick} aria-label="PARALLAX home">
      <span className="logo-mark">
        <i />
        <i />
      </span>
      <span>PARALLAX</span>
    </button>
  );
}

function Button({
  children,
  onClick,
  variant = "primary",
  icon,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "ghost";
  icon?: IconName;
}) {
  return (
    <button className={`button ${variant}`} onClick={onClick}>
      {children}
      {icon && <Icon name={icon} />}
    </button>
  );
}

function Glass({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`glass ${className}`}>{children}</div>;
}

function Header({ screen, setScreen }: { screen: Screen; setScreen: (s: Screen) => void }) {
  const links: [Screen, string][] = [
    ["explore", "Sky Explorer"],
    ["timelapse", "Timelapse"],
    ["dial", "Distance Dial"],
    ["compare", "Compare"],
    ["about", "Methodology"],
  ];
  return (
    <header className="topbar">
      <Logo onClick={() => setScreen("home")} />
      <nav className="nav-pill" aria-label="Primary navigation">
        {links.map(([key, label]) => (
          <button
            key={key}
            className={screen === key ? "active" : ""}
            onClick={() => setScreen(key)}
          >
            {label}
          </button>
        ))}
      </nav>
      <Button variant="secondary" onClick={() => setScreen("explore")}>
        Open survey <Icon name="arrow" />
      </Button>
    </header>
  );
}

function Background() {
  return (
    <div className="space-bg" aria-hidden="true">
      <div className="orb orb-a" />
      <div className="orb orb-b" />
      <div className="orb orb-c" />
      <div className="stars" />
    </div>
  );
}

function Home({ setScreen }: { setScreen: (s: Screen) => void }) {
  return (
    <main className="home">
      <section className="hero">
        <div className="eyebrow">
          <span />
          <Icon name="spark" size={15} /> NASA SPACE APPS · PLANET X & SPHEREx
        </div>
        <h1>
          See what the sky
          <br />
          <em>hasn’t told us yet.</em>
        </h1>
        <p>
          Explore the infrared universe. Trace faint motion across time. Help investigate the
          signals that could reveal a distant ninth planet.
        </p>
        <div className="hero-actions">
          <Button onClick={() => setScreen("explore")} icon="arrow">
            Explore the sky
          </Button>
          <Button variant="secondary" onClick={() => setScreen("about")}>
            How it works
          </Button>
        </div>
        <div className="signal-readout">
          <span>SPHEREx ALL-SKY SURVEY</span>
          <b>102</b>
          <small>spectral bands</small>
          <i />
          <b>450M+</b>
          <small>galaxies targeted</small>
        </div>
      </section>
      <section className="features">
        <Glass className="feature main-feature">
          <div
            className="feature-image"
            style={{
              backgroundImage: `linear-gradient(180deg, transparent, rgba(5,6,15,.9)), url(${spaceImage})`,
            }}
          >
            <span className="target target-a" />
            <span className="target target-b" />
            <div className="scanline" />
          </div>
          <div className="feature-copy">
            <span className="num">01</span>
            <div>
              <h3>Search the infrared sky</h3>
              <p>Browse published SPHEREx cutouts by field and date.</p>
            </div>
            <button aria-label="Open sky explorer" onClick={() => setScreen("explore")}>
              <Icon name="arrow" />
            </button>
          </div>
        </Glass>
        <Glass className="feature">
          <div className="mini-orbit">
            <span className="sun" />
            <span className="ring r1" />
            <span className="ring r2" />
            <span className="planet" />
          </div>
          <div className="feature-copy">
            <span className="num">02</span>
            <div>
              <h3>Inspect subtle motion</h3>
              <p>Play every epoch as a timelapse and watch what moves.</p>
            </div>
            <button aria-label="Open timelapse" onClick={() => setScreen("timelapse")}>
              <Icon name="play" />
            </button>
          </div>
        </Glass>
        <Glass className="feature">
          <div className="spectrum-mini">
            <svg viewBox="0 0 300 105" preserveAspectRatio="none">
              <path d="M0 84 C25 78, 38 84, 55 58 S80 25, 102 66 S132 83, 150 49 S179 18, 195 58 S226 75, 241 42 S270 30, 300 10" />
              <path
                className="area"
                d="M0 84 C25 78,38 84,55 58 S80 25,102 66 S132 83,150 49 S179 18,195 58 S226 75,241 42 S270 30,300 10 V105 H0Z"
              />
            </svg>
          </div>
          <div className="feature-copy">
            <span className="num">03</span>
            <div>
              <h3>Evaluate candidates</h3>
              <p>Weigh spectral, motion, and quality evidence together.</p>
            </div>
          </div>
        </Glass>
      </section>
      <section className="steps">
        <div>
          <small>THE SEARCH, SIMPLIFIED</small>
          <h2>From photons to a possibility.</h2>
        </div>
        {["Filter the survey", "Inspect candidates", "Model an orbit"].map((x, i) => (
          <div className="step" key={x}>
            <span>0{i + 1}</span>
            <p>{x}</p>
            {i < 2 && <Icon name="chevron" />}
          </div>
        ))}
      </section>
      <footer>
        <Logo onClick={() => setScreen("home")} />
        <span>Built for NASA Space Apps Challenge 2025</span>
        <span>Data: NASA · JPL · Caltech</span>
      </footer>
    </main>
  );
}

function About() {
  return (
    <main className="content-screen about-screen">
      <div className="section-title">
        <small>SCIENCE & METHODOLOGY</small>
        <h1>
          Finding motion in
          <br />
          an infrared universe.
        </h1>
        <p>
          Compare repeat SPHEREx observations and learn how wavelength affects the differences you see.
        </p>
      </div>
      <Glass className="article">
        <section>
          <span className="article-num">01</span>
          <div>
            <small>THE MISSION</small>
            <h2>A spectrum for every point in the sky.</h2>
            <p>
              SPHEREx surveys the entire sky in 102 infrared colors. While its primary mission
              traces the origin of the universe and the history of galaxies, its repeated sky
              coverage creates a powerful record of change over time.
            </p>
          </div>
        </section>
        <section>
          <span className="article-num">02</span>
          <div>
            <small>THE PIPELINE</small>
            <h2>From archive to comparison</h2>
            <div className="pipeline">
              {[
                "Ingest survey epochs",
                "Align cutouts",
                "Match wavelengths",
                "Compare epochs",
              ].map((x, i) => (
                <div key={x}>
                  <span>
                    <Icon
                      name={i === 0 ? "spark" : i === 1 ? "grid" : i === 2 ? "orbit" : "check"}
                    />
                  </span>
                  <b>{x}</b>
                  {i < 3 && <Icon name="chevron" />}
                </div>
              ))}
            </div>
          </div>
        </section>
        <section>
          <span className="article-num">03</span>
          <div>
            <small>DATA SOURCES</small>
            <h2>Built on open science.</h2>
            <p>
              The observation explorer displays SPHEREx Level 2 cutouts from NASA/IPAC IRSA. Each real frame links to its archive product. The synthetic distance dial illustrates the method.
            </p>
            <div className="source-chips">
              <span>NASA SPHEREx</span>
              <a href="https://irsa.ipac.caltech.edu/Missions/spherex.html">NASA/IPAC IRSA</a>
            </div>
          </div>
        </section>
      </Glass>
    </main>
  );
}

function MobileNav({ screen, setScreen }: { screen: Screen; setScreen: (s: Screen) => void }) {
  const items: [Screen, IconName, string][] = [
    ["home", "spark", "Home"],
    ["explore", "grid", "Explore"],
    ["timelapse", "play", "Timelapse"],
    ["dial", "orbit", "Dial"],
    ["about", "book", "About"],
  ];
  return (
    <nav className="mobile-nav">
      {items.map(([s, i, l]) => (
        <button key={s} className={screen === s ? "active" : ""} onClick={() => setScreen(s)}>
          <Icon name={i} />
          <span>{l}</span>
        </button>
      ))}
    </nav>
  );
}

const screens: Screen[] = ["home", "explore", "timelapse", "dial", "compare", "about"];

export default function App() {
  const [route, setRoute] = useState(location.hash);
  const [index, setIndex] = useState<FieldSummary[]>();
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ id: string; field?: Awaited<ReturnType<typeof loadField>>; error?: string }>();
  const [path, search] = route.slice(2).split("?");
  const [screenName, fieldId] = path.split("/");
  const screen = screens.find(value => value === screenName) ?? "home";
  const active = screen === "explore" || screen === "compare" || screen === "timelapse";
  const catalog = index?.filter(item => item.status !== "pending");
  const selected = catalog?.find(item => item.field_id === fieldId)
    ?? catalog?.find(item => item.synthetic === false) ?? catalog?.[0];
  const id = active ? selected?.field_id : undefined;
  const field = result?.id === id ? result?.field : undefined;
  const fieldError = result?.id === id ? result?.error : undefined;

  useEffect(() => {
    const update = () => { setRoute(location.hash); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadIndex(controller.signal).then(setIndex).catch(error => {
      if (!controller.signal.aborted) setError(error.message);
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    loadField(id, controller.signal).then(field => {
      if (!controller.signal.aborted) setResult({ id, field });
    }).catch(error => {
      if (!controller.signal.aborted) setResult({ id, error: error.message });
    });
    return () => controller.abort();
  }, [id]);

  const navigate = (next: Screen, nextId = selected?.field_id) => {
    location.hash = "/" + next + (nextId && next !== "home" && next !== "about" && next !== "dial" ? "/" + nextId : "");
  };

  const timeline = useMemo(() => {
    if (!field) return [];
    const frames = new Map(field.frames.map(frame => [frame.id, frame]));
    const ordered = field.timeline?.flatMap(entry => frames.get(entry.frame_id) ?? [])
      ?? [...field.frames].sort((a, b) => Date.parse(a.obs_time_utc) - Date.parse(b.obs_time_utc));
    return ordered.map(frame => ({
      date: frame.obs_time_utc.slice(0, 10),
      wavelengthUm: frame.wavelength_um,
      detector: frame.detector,
      src: imageUrl(field.field_id, frame.png),
      sourceUrl: field.provenance.synthetic ? undefined : frame.source_url,
    }));
  }, [field]);

  return (
    <div className="app">
      <Background />
      <Header screen={screen} setScreen={navigate} />
      {screen === "home" && <Home setScreen={navigate} />}
      {screen === "about" && <About />}
      {screen === "dial" && <ErrorBoundary><DistanceDial /></ErrorBoundary>}
      {active && <main className="content-screen survey-observations">
        <div className="section-title">
          <h1>{selected?.title ?? "Sky Explorer"}</h1>
          <label>Sky field <select value={selected?.field_id ?? ""} onChange={event => navigate(screen, event.target.value)}>
            {catalog?.map(item => <option key={item.field_id} value={item.field_id}>{item.title}</option>)}
          </select></label>
        </div>
        {(error || fieldError) && <p role="alert">{error || fieldError}</p>}
        {!field && !error && !fieldError && <p role="status">{catalog?.length === 0 ? "No fields available." : "Loading observations…"}</p>}
        {field && <ErrorBoundary key={screen + "/" + field.field_id}>
          {screen === "timelapse" && timeline.length > 0
            ? <Timelapse frames={timeline} synthetic={field.provenance.synthetic} title={field.title} backdrop={spaceImage} onBack={() => navigate("explore")} />
            : <SimpleViewer field={field} survey search={search ?? (screen === "compare" ? "mode=compare" : undefined)} />}
        </ErrorBoundary>}
      </main>}
      <MobileNav screen={screen} setScreen={navigate} />
    </div>
  );
}
