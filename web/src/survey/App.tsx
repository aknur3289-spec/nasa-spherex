import { useEffect, useMemo, useState } from "react";
import { Timelapse } from "./Timelapse";
import { DistanceDial } from "./DistanceDial";
import { ParallaxLab } from "./ParallaxLab";
import { imageUrl, loadField, loadIndex } from "../data/loader";
import type { FieldSummary } from "../contract";
import { SkyExplorer } from "./SkyExplorer";
import { ComparePairs } from "./ComparePairs";
import { LiveField } from "../live/LiveField";
import { TrackField } from "../live/TrackField";
import { AnyPoint } from "./AnyPoint";
import { friendly , FRIENDLY } from "./fields";
import { ErrorBoundary } from "../viewer/ErrorBoundary";

type Screen = "home" | "explore" | "timelapse" | "lab" | "dial" | "compare" | "about";
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
    ["lab", "Parallax Lab"],
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
      <Button variant="secondary" onClick={() => setScreen("lab")}>
        Try the simulator <Icon name="arrow" />
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

function Home({ setScreen }: { setScreen: (s: Screen, id?: string) => void }) {
  return (
    <main className="home">
      <section className="hero">
        <div className="eyebrow">
          <span />
          <Icon name="spark" size={15} /> NASA SPACE APPS 2026 · PLANET X & SPHEREx
        </div>
        <h1>
          How do you find a hidden planet?
          <br />
          <em>Look for a dot that moves.</em>
        </h1>
        <p>
          NASA's SPHEREx telescope photographs the whole sky again and again. A hidden planet would be one faint dot that
          shifts between those images, lost among millions of stars, detector artefacts and colour changes. PARALLAX is an
          open pipeline and a hands-on tool that finds dots that really move, rejects the fakes, and measures how far away
          they are. We tested it blind on real SPHEREx data: <b>it found Neptune on its own and measured its distance
          within 0.13% of NASA JPL.</b>
        </p>
        <div className="hero-actions">
          <Button onClick={() => setScreen("lab")} icon="arrow">
            Try the parallax simulator
          </Button>
          <Button variant="secondary" onClick={() => setScreen("timelapse", "neptune-track")}>
            Watch Neptune move
          </Button>
        </div>
        <AnyPoint />
        <div className="hero-result glass">
          <div>
            <small>BLIND TEST · NO JPL USED</small>
            <b>
              29.93 <span>± 0.02 AU</span>
            </b>
            <em>Neptune found by our detector in 64 of 74 real image differences</em>
          </div>
          <i />
          <div>
            <small>NASA JPL REFERENCE</small>
            <b>
              29.89 <span>AU</span>
            </b>
            <em>Used only to grade · difference 0.13%</em>
          </div>
        </div>
      </section>

      <section className="why">
        <div className="how-head">
          <small>WHY IT MATTERS</small>
          <h2>The problem, what we built, what we proved.</h2>
        </div>
        <div className="why-grid">
          <div className="glass why-card">
            <small>THE PROBLEM</small>
            <h3>A moving dot hides among fakes</h3>
            <p>
              Astronomers suspect an unseen planet beyond Neptune. SPHEREx revisits every point of the sky every six months,
              so it could catch such a dot moving. But most "changes" between two SPHEREx images are fake: each image is taken
              in a slightly different infrared colour, bright objects leave ghosts, and stars do not subtract cleanly.
            </p>
          </div>
          <div className="glass why-card">
            <small>WHAT WE BUILT</small>
            <h3>From raw NASA images to a distance</h3>
            <ul>
              <li>Fair image pairs only (same colour, trust badge)</li>
              <li>Automatic detection of new, moving sources</li>
              <li>Rejection of static stars, optical ghosts and glare</li>
              <li>Distance from two seasons with a parallax + orbit model</li>
              <li>A simulator anyone can use to learn and test it</li>
            </ul>
          </div>
          <div className="glass why-card">
            <small>WHAT WE PROVED</small>
            <h3>It works blind on real data</h3>
            <p>
              Without being told where Neptune is, the pipeline found it in 64 of 74 image differences, kept it as the only
              real moving track, and measured 29.93 AU (JPL: 29.89 AU). We also found that SPHEREx's own OUTLIER/TRANSIENT
              flags mark moving objects — masking them, as usual, throws away real detections.
            </p>
          </div>
        </div>
        <p className="why-not">
          Not yet: a Planet-Nine-like object is far fainter than one SPHEREx image can show. The next step is Shift &amp;
          Stack — adding many images along each trial path — which this pipeline is built to feed.
        </p>
      </section>

      <section className="how-steps">
        <div className="how-head">
          <small>THE METHOD IN THREE STEPS</small>
          <h2>Find it. Check it. Measure it.</h2>
        </div>
        {([
          ["Find what moves", "Flip between images of the same patch taken months apart. Stars stay put; a planet or asteroid shifts.", "Watch Neptune move", () => setScreen("timelapse", "neptune-track")],
          ["Check it is not a colour trick", "SPHEREx takes every image in a slightly different infrared colour, so stars can seem to change. We only trust pairs taken in the same colour (green badge).", "Try a fair comparison", () => setScreen("compare", "m101")],
          ["Measure the distance", "Nearer objects shift more. In the Parallax Lab you turn the distance until the prediction lands on the detections: that distance is the measurement.", "Open the simulator", () => setScreen("lab")],
        ] as [string, string, string, () => void][]).map(([h, p, cta, go], i) => (
          <button className="glass how-card how-card-link" key={h} onClick={go}>
            <span>{i + 1}</span>
            <h3>{h}</h3>
            <p>{p}</p>
            <em>{cta} →</em>
          </button>
        ))}
      </section>

      <section className="features">
        <Glass className="feature main-feature">
          <div className="feature-image feature-dial" aria-hidden="true">
            <img src="data/dial/neptune_stamp.png" alt="" />
            <span className="fd-neptune" />
            <span className="fd-cross" />
            <span className="fd-label">Neptune · SPHEREx</span>
            <span className="fd-miss">blind fit · 29.93 AU</span>
          </div>
          <div className="feature-copy">
            <span className="num">01</span>
            <div>
              <h3>Parallax Lab</h3>
              <p>A live simulator, a hide-the-planet game, and Neptune's blind test on real SPHEREx data.</p>
            </div>
            <button aria-label="Open the Parallax Lab" onClick={() => setScreen("lab")}>
              <Icon name="arrow" />
            </button>
          </div>
        </Glass>
        <Glass className="feature">
          <div className="mini-film" aria-hidden="true">
            {["neptune-track", "nep", "ecl"].map((id) => (
              <img key={id} src={imageUrl(id, id === "neptune-track" ? "color.png" : "thumb.png")} alt="" loading="lazy" />
            ))}
          </div>
          <div className="feature-copy">
            <span className="num">02</span>
            <div>
              <h3>Neptune moving against fixed stars</h3>
              <p>Watch the known planet move through real SPHEREx images of a fixed sky field.</p>
              <small>SPHEREx true-colour: 0.75–1.10 / 1.10–1.70 / 1.70–2.42 um, real data</small>
            </div>
            <button aria-label="Watch Neptune timelapse" onClick={() => setScreen("timelapse", "neptune-track")}>
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
          ["Curious people & students", "Move Earth around the Sun, hide a planet and find it again, then measure Neptune on real NASA data.", "lab", "Start playing"],
          ["Volunteers & citizen scientists", "If you search for faint movers in projects like Backyard Worlds, see which image pairs you can compare and which you cannot.", "compare", "Check image pairs"],
          ["Researchers", "Blind detection and distance on real SPHEREx data, a mover-aware flag policy, injection-recovery depth, and open code.", "about", "Read the method"],
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
    "The image cutouts were downloaded around Neptune's position, so the search area was chosen with prior knowledge, even though the detector, linking and distance fit never use the ephemeris.",
    "Neptune proves the geometry, not the sensitivity: Neptune is bright and probably saturated.",
    "Science team's earlier single-pair work: Neptune 29.95 ± 0.03 AU from 1,007 pairs; Uranus 19.42 AU is preliminary.",
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
          Our detector found Neptune by itself in real SPHEREx images from June and December 2025 and measured
          29.93 ± 0.02 AU from those detections alone. JPL Horizons (29.89 AU) was used only to grade the answer.
        </p>
      </div>
      <section className="stat-grid about-stats">
        {[
          ["BLIND TEST", "29.93 AU", "± 0.02 · no JPL used"],
          ["JPL HORIZONS", "29.89 AU", "0.13% difference"],
          ["FOUND", "64 / 74", "image differences"],
          ["ONE-IMAGE DEPTH", "≈ 1/500", "of Neptune's brightness (50% recovered)"],
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
            <small>THE BLIND TEST</small>
            <h2>Find it first, then measure it.</h2>
            <p>
              1) Subtract a reference image of the same sky taken at another time (Neptune absent). 2) Keep new sources
              above 5σ whose flux is not in the reference. 3) Link detections from different exposures into tracks and
              reject static sources, optical ghosts (fixed detector offset from a bright mover) and glare companions.
              4) Fit one distance with a circular-orbit model from the June track to the December track. Only then compare
              with JPL Horizons.
            </p>
            <img className="about-figure" src="figures/blind_test.png" alt="Blind test: linked tracks, distance curve with one sharp minimum at 29.93 AU, and injection recovery curve" loading="lazy" />
          </div>
        </section>
        <section>
          <span className="article-num">04</span>
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
          <span className="article-num">05</span>
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
    ["lab", "orbit", "Lab"],
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

const screens: Screen[] = ["home", "explore", "timelapse", "lab", "dial", "compare", "about"];

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
  const track = useMemo(() => {
    if (screenName !== "track") return undefined;
    const n = new URLSearchParams(search ?? "").get("name");
    return n && n.trim() ? n.trim().slice(0, 60) : undefined;
  }, [screenName, search]);
  const screen = live || track ? "explore" : screens.find(value => value === screenName) ?? "home";
  const active = screen === "compare" || screen === "timelapse";
  const catalog = index?.filter(item => item.status !== "pending" && item.synthetic === false);
  const [enhanced, setEnhanced] = useState(true);
  const selected = catalog?.find(item => item.field_id === fieldId)
    ?? (screen === "timelapse" ? catalog?.find(item => item.field_id === "neptune-track") : undefined)
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
    location.hash = "/" + next + (nextId && next !== "home" && next !== "about" && next !== "dial" && next !== "lab" ? "/" + nextId : "");
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
      maskSrc: frame.mask_png ? imageUrl(field.field_id, frame.mask_png) : undefined,
      targetRadec: frame.target_radec,
      center: frame.center,
      widthPx: frame.width_px,
      heightPx: frame.height_px,
      sourceUrl: field.provenance.synthetic ? undefined : frame.source_url,
    }));
  }, [field]);
  const colorCaption = field?.color_bands_um
    ? `SPHEREx true-colour: ${field.color_bands_um.map(([lo, hi]) => `${lo.toFixed(2)}–${hi.toFixed(2)}`).join(" / ")} um, real data`
    : undefined;

  return (
    <div className="app">
      <Background />
      <Header screen={screen} setScreen={navigate} />
      {screen === "home" && <Home setScreen={navigate} />}
      {screen === "about" && <About />}
      {screen === "lab" && <ErrorBoundary><ParallaxLab onOpenDial={() => navigate("dial")} /></ErrorBoundary>}
      {screen === "dial" && <ErrorBoundary><DistanceDial /></ErrorBoundary>}
      {live && <ErrorBoundary key={route}><LiveField ra={live.ra} dec={live.dec} label={live.label} backdrop={spaceImage} onBack={() => navigate("explore")} /></ErrorBoundary>}
      {track && <ErrorBoundary key={route}><TrackField name={track} backdrop={spaceImage} onBack={() => history.back()} /></ErrorBoundary>}
      {screen === "explore" && !live && !track && (catalog
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
        <AnyPoint compact />
        <p className="examples-label">Or open a ready example (loads instantly, prepared and checked in advance):</p>
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
        {selected && FRIENDLY[selected.field_id]?.look && <div className={`glass look-box ${FRIENDLY[selected.field_id].role ?? ""}`}>
          <small>{FRIENDLY[selected.field_id].role === "control" ? "CONTROL FIELD · WHAT TO EXPECT" : "WHAT TO LOOK AT"}</small>
          <p><b>{friendly(selected).name}.</b> {friendly(selected).text}</p>
          <p>{FRIENDLY[selected.field_id].look}</p>
        </div>}
        {(error || fieldError) && <p role="alert">{error || fieldError}</p>}
        {!field && !error && !fieldError && <p role="status">{catalog?.length === 0 ? "No fields available." : "Loading observations…"}</p>}
        {field && <ErrorBoundary key={screen + "/" + field.field_id}>
          {screen === "timelapse" && timeline.length > 0
            ? <Timelapse frames={timeline} synthetic={field.provenance.synthetic} title={friendly(selected).name} backdrop={spaceImage} onBack={() => navigate("explore")} heroSrc={field.color_png ? imageUrl(field.field_id, field.color_png) : undefined} heroCaption={colorCaption} />
            : <ComparePairs field={field} />}
        </ErrorBoundary>}
      </main>}
      <MobileNav screen={screen} setScreen={navigate} />
    </div>
  );
}
