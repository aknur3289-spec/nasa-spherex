import { useEffect, useMemo, useState } from "react";
import { Timelapse } from "./Timelapse";
import { DistanceDial } from "./DistanceDial";
import { imageUrl, loadField, loadIndex } from "../data/loader";
import type { FieldSummary } from "../contract";
import { SkyExplorer } from "./SkyExplorer";
import { ComparePairs } from "./ComparePairs";
import { LiveField } from "../live/LiveField";
import { friendly } from "./fields";
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
      <Button variant="secondary" onClick={() => setScreen("dial")}>
        Play the dial <Icon name="arrow" />
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
          <Icon name="spark" size={15} /> NASA SPACE APPS 2026 · PLANET X & SPHEREx
        </div>
        <h1>
          Hunt for a distant planet
          <br />
          <em>with real NASA data.</em>
        </h1>
        <p>
          Turn a dial, watch a crosshair land on Neptune in a real SPHEREx image, and see how astronomers
          measure distances across the Solar System. No astronomy degree needed.
        </p>
        <div className="hero-actions">
          <Button onClick={() => setScreen("dial")} icon="arrow">
            Play the Distance Dial
          </Button>
          <Button variant="secondary" onClick={() => setScreen("timelapse")}>
            Watch the sky change
          </Button>
        </div>
        <div className="hero-result glass">
          <div>
            <small>OUR MEASUREMENT</small>
            <b>
              29.95 <span>± 0.03 AU</span>
            </b>
            <em>Neptune, from 1,007 pairs of real SPHEREx images</em>
          </div>
          <i />
          <div>
            <small>NASA JPL REFERENCE</small>
            <b>
              29.89 <span>AU</span>
            </b>
            <em>Difference +0.2%</em>
          </div>
        </div>
      </section>

      <section className="how-steps">
        <div className="how-head">
          <small>HOW IT WORKS</small>
          <h2>Three steps. One real measurement.</h2>
        </div>
        {[
          ["Pick a distance", "Guess how far away the object is with a slider."],
          ["See the prediction", "Our model shows where it should appear six months later."],
          ["Find the closest match", "The guess that lands nearest the real image is the distance."],
        ].map(([h, p], i) => (
          <div className="glass how-card" key={h}>
            <span>{i + 1}</span>
            <h3>{h}</h3>
            <p>{p}</p>
          </div>
        ))}
      </section>

      <section className="features">
        <Glass className="feature main-feature">
          <div className="feature-image feature-dial" aria-hidden="true">
            <img src="data/dial/neptune_stamp.png" alt="" />
            <span className="fd-neptune" />
            <span className="fd-cross" />
            <span className="fd-label">Neptune · SPHEREx</span>
            <span className="fd-miss">closest match · 29.9 AU</span>
          </div>
          <div className="feature-copy">
            <span className="num">01</span>
            <div>
              <h3>Distance Dial</h3>
              <p>Measure Neptune yourself on real data, the way you would hunt for Planet Nine.</p>
            </div>
            <button aria-label="Open the Distance Dial" onClick={() => setScreen("dial")}>
              <Icon name="arrow" />
            </button>
          </div>
        </Glass>
        <Glass className="feature">
          <div className="mini-film" aria-hidden="true">
            {["m101", "nep", "ecl"].map((id) => (
              <img key={id} src={imageUrl(id, "thumb.png")} alt="" loading="lazy" />
            ))}
          </div>
          <div className="feature-copy">
            <span className="num">02</span>
            <div>
              <h3>Timelapse</h3>
              <p>Play real SPHEREx images of one patch of sky in date order and see what changes.</p>
            </div>
            <button aria-label="Open timelapse" onClick={() => setScreen("timelapse")}>
              <Icon name="play" />
            </button>
          </div>
        </Glass>
        <Glass className="feature">
          <div className="trust-mini">
            <span className="t-high">High trust · same band</span>
            <span className="t-mid">Medium · 3% apart</span>
            <span className="t-low">Low · colour changes</span>
          </div>
          <div className="feature-copy">
            <span className="num">03</span>
            <div>
              <h3>Which images can you trust?</h3>
              <p>Compare pairs and see when a change is real motion, not a colour effect.</p>
            </div>
            <button aria-label="Open compare" onClick={() => setScreen("compare")}>
              <Icon name="arrow" />
            </button>
          </div>
        </Glass>
      </section>

      <section className="audience">
        <div className="how-head">
          <small>WHO IT IS FOR</small>
          <h2>Anyone can try hunting a distant planet.</h2>
        </div>
        {[
          ["Curious people & students", "Move a slider, watch the crosshair hit or miss a real NASA image, and learn how distance is measured in space.", "dial", "Start playing"],
          ["Volunteers & citizen scientists", "If you search for faint movers in projects like Backyard Worlds, see which image pairs you can compare and which you cannot.", "compare", "Check image pairs"],
          ["Researchers", "Method validated on Neptune and Uranus, a trust badge for every pair, and how many frames a faint object would need.", "about", "Read the method"],
        ].map(([h, p, to, cta]) => (
          <div className="glass audience-card" key={h}>
            <h3>{h}</h3>
            <p>{p}</p>
            <button className="text-link" onClick={() => setScreen(to as Screen)}>
              {cta} <Icon name="arrow" size={14} />
            </button>
          </div>
        ))}
      </section>

      <footer>
        <Logo onClick={() => setScreen("home")} />
        <span>Built for NASA Space Apps Challenge 2026</span>
        <span>Data: NASA SPHEREx via IRSA · JPL Horizons</span>
      </footer>
    </main>
  );
}

function About() {
  const limits = [
    "Neptune proves the geometry, not the sensitivity: Neptune is bright and probably saturated.",
    "The model assumes a circular orbit near the ecliptic. An inclined orbit can bias the result — one 20° test case gave −2.8%.",
    "The two images are at 0.968 µm and 1.259 µm. Measured positions agree with JPL Horizons within 27″ (4.5 px); this limits any colour effect to 0.10 AU.",
    "A faint Planet Nine (V ≈ 21.9–22.7) is far below the single-frame limit (AB 18.4); many frames would have to be stacked.",
  ];
  return (
    <main className="content-screen about-screen">
      <div className="section-title">
        <small>SCIENCE & METHODOLOGY</small>
        <h1>
          Measuring a distance
          <br />
          from two pictures.
        </h1>
        <p>
          From two real SPHEREx exposures six months apart we measured Neptune at 29.95 ± 0.03 AU — using only one
          measured position, its time and a trial distance. No ephemeris of the target.
        </p>
      </div>
      <section className="stat-grid about-stats">
        {[
          ["NEPTUNE", "29.95 AU", "± 0.03 · 1,007 pairs"],
          ["JPL HORIZONS", "29.89 AU", "+0.2%"],
          ["URANUS", "19.42 AU", "± 0.02 · vs 19.50 (−0.4%)"],
          ["PARALLAX ONLY", "up to 49%", "error, season-dependent"],
        ].map((x) => (
          <div className="glass stat" key={x[0]}>
            <small>{x[0]}</small>
            <strong>{x[1]}</strong>
            <span>{x[2]}</span>
          </div>
        ))}
      </section>
      <Glass className="article">
        <section>
          <span className="article-num">01</span>
          <div>
            <small>THE MISSION</small>
            <h2>A spectrum for every point in the sky.</h2>
            <p>
              SPHEREx surveys the entire sky in 102 infrared colours and comes back to the same places every six
              months. That repeat coverage is a record of what moves.
            </p>
          </div>
        </section>
        <section>
          <span className="article-num">02</span>
          <div>
            <small>THE METHOD</small>
            <h2>Parallax plus orbital motion.</h2>
            <p>
              Earth moves around the Sun, so a distant object seems to shift against the stars. The object also moves
              along its own orbit. We predict the position six months later for many trial distances and keep the one
              that lands closest to the real image. Ignoring orbital motion gives errors from −23.1% to +48.6%.
            </p>
            <div className="pipeline">
              {["Measure a position", "Try a distance", "Predict 6 months later", "Keep the closest match"].map((x, i) => (
                <div key={x}>
                  <span>
                    <Icon name={i === 0 ? "spark" : i === 1 ? "grid" : i === 2 ? "orbit" : "check"} />
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
            <small>LIMITATIONS</small>
            <h2>What this does and does not show.</h2>
            <ul className="about-limits">
              {limits.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </div>
        </section>
        <section>
          <span className="article-num">04</span>
          <div>
            <small>DATA SOURCES</small>
            <h2>Built on open science.</h2>
            <p>
              Images are SPHEREx Level 2 cutouts from NASA/IPAC IRSA; each real frame links to its archive product.
              Reference distances come from JPL Horizons.
            </p>
            <div className="source-chips">
              <span>NASA SPHEREx</span>
              <a href="https://irsa.ipac.caltech.edu/Missions/spherex.html">NASA/IPAC IRSA</a>
              <a href="https://ssd.jpl.nasa.gov/horizons/">JPL Horizons</a>
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
  const live = useMemo(() => {
    if (screenName !== "live") return undefined;
    const q = new URLSearchParams(search ?? "");
    const ra = Number(q.get("ra")), dec = Number(q.get("dec"));
    if (!Number.isFinite(ra) || !Number.isFinite(dec) || Math.abs(dec) > 90) return undefined;
    return { ra, dec, label: q.get("name") || `RA ${ra.toFixed(3)}°, Dec ${dec.toFixed(3)}°` };
  }, [screenName, search]);
  const screen = live ? "explore" : screens.find(value => value === screenName) ?? "home";
  const active = screen === "compare" || screen === "timelapse";
  const catalog = index?.filter(item => item.status !== "pending" && item.synthetic === false);
  const [enhanced, setEnhanced] = useState(true);
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
      {live && <ErrorBoundary key={route}><LiveField ra={live.ra} dec={live.dec} label={live.label} backdrop={spaceImage} onBack={() => navigate("explore")} /></ErrorBoundary>}
      {screen === "explore" && !live && (catalog
        ? <ErrorBoundary><SkyExplorer catalog={catalog} go={(s, nextId) => navigate(s, nextId)} /></ErrorBoundary>
        : <main className="content-screen"><p role="status">{error || "Loading sky fields…"}</p></main>)}
      {active && <main className={`content-screen survey-observations ${enhanced ? "enhanced" : "raw"}`}>
        {screen !== "timelapse" && <div className="obs-head">
          <div>
            <small>COMPARE TWO IMAGES · REAL SPHEREx DATA</small>
            <h1>{friendly(selected).name}</h1>
            <p>{friendly(selected).text}</p>
          </div>
          <button className={`button secondary ${enhanced ? "" : "tl-on"}`} aria-pressed={!enhanced} onClick={() => setEnhanced(!enhanced)}>
            {enhanced ? "Show raw pixels" : "Smooth view"}
          </button>
        </div>}
        <div className="field-cards" role="group" aria-label="Choose a sky field">
          {catalog?.map(item => <button key={item.field_id} className={`glass field-card ${item.field_id === selected?.field_id ? "active" : ""}`}
            aria-pressed={item.field_id === selected?.field_id} onClick={() => navigate(screen, item.field_id)}>
            <img src={imageUrl(item.field_id, item.thumbnail ?? "thumb.png")} alt="" loading="lazy" />
            <span>
              <b>{friendly(item).name}</b>
              <small>{item.n_frames ?? "?"} images · {item.date_range ? item.date_range.start_utc.slice(0, 7) + " → " + item.date_range.end_utc.slice(0, 7) : ""}</small>
            </span>
          </button>)}
        </div>
        {(error || fieldError) && <p role="alert">{error || fieldError}</p>}
        {!field && !error && !fieldError && <p role="status">{catalog?.length === 0 ? "No fields available." : "Loading observations…"}</p>}
        {field && <ErrorBoundary key={screen + "/" + field.field_id}>
          {screen === "timelapse" && timeline.length > 0
            ? <Timelapse frames={timeline} synthetic={field.provenance.synthetic} title={friendly(selected).name} backdrop={spaceImage} onBack={() => navigate("explore")} />
            : <ComparePairs field={field} />}
        </ErrorBoundary>}
      </main>}
      <MobileNav screen={screen} setScreen={navigate} />
    </div>
  );
}
