import { useMemo, useState } from "react";
import { Timelapse } from "./Timelapse";

type Screen = "home" | "explore" | "detail" | "timelapse" | "orbit" | "compare" | "about";
type IconName =
  | "arrow"
  | "search"
  | "spark"
  | "grid"
  | "orbit"
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
const nebulaImage =
  "https://images.unsplash.com/photo-1708112292872-fd5612affa79?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=85&w=1800";

const candidates = [
  {
    id: "PX-0714",
    ra: "06h 42m 18.7s",
    dec: "−23° 41′ 09″",
    confidence: 94,
    motion: 1.82,
    mag: 18.4,
    status: "High priority",
  },
  {
    id: "PX-1029",
    ra: "19h 08m 44.2s",
    dec: "+08° 13′ 22″",
    confidence: 87,
    motion: 1.47,
    mag: 19.1,
    status: "Review",
  },
  {
    id: "PX-0841",
    ra: "11h 26m 03.9s",
    dec: "−41° 02′ 51″",
    confidence: 79,
    motion: 1.21,
    mag: 20.0,
    status: "Unverified",
  },
];

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
          <small>sources mapped</small>
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
              <p>Navigate SPHEREx survey data across 102 spectral bands.</p>
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

function CandidateCard({
  c,
  onClick,
  selected = false,
}: {
  c: (typeof candidates)[0];
  onClick: () => void;
  selected?: boolean;
}) {
  return (
    <button className={`candidate ${selected ? "selected" : ""}`} onClick={onClick}>
      <div className="candidate-thumb" style={{ backgroundImage: `url(${spaceImage})` }}>
        <span />
      </div>
      <div className="candidate-copy">
        <div>
          <b>{c.id}</b>
          <span className={`chip ${c.confidence > 90 ? "success" : ""}`}>{c.status}</span>
        </div>
        <small>RA {c.ra}</small>
        <small>Dec {c.dec}</small>
      </div>
      <div
        className="score"
        style={{ "--score": `${c.confidence * 3.6}deg` } as React.CSSProperties}
      >
        <span>{c.confidence}</span>
      </div>
    </button>
  );
}

function Explorer({
  setScreen,
  selectCandidate,
}: {
  setScreen: (s: Screen) => void;
  selectCandidate: (i: number) => void;
}) {
  const [confidence, setConfidence] = useState(72);
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () =>
      candidates.filter(
        (c) => c.confidence >= confidence && c.id.toLowerCase().includes(query.toLowerCase()),
      ),
    [confidence, query],
  );
  return (
    <main className="app-screen explorer">
      <div
        className="map-canvas"
        style={{
          backgroundImage: `linear-gradient(rgba(5,6,15,.26),rgba(5,6,15,.45)),url(${spaceImage})`,
        }}
      >
        <div className="map-grid" />
        {candidates.map((c, i) => (
          <button
            key={c.id}
            className={`map-target mt-${i}`}
            onClick={() => {
              selectCandidate(i);
              setScreen("detail");
            }}
            aria-label={`Open ${c.id}`}
          >
            <span />
            <label>
              {c.id}
              <small>{c.confidence}% match</small>
            </label>
          </button>
        ))}
        <div className="coordinates">
          RA 08h 24m 12s <span /> DEC −18° 42′ 09″
        </div>
      </div>
      <Glass className="filter-panel panel">
        <div className="panel-title">
          <div>
            <small>SURVEY CONTROLS</small>
            <h3>Filter the sky</h3>
          </div>
          <Icon name="filter" />
        </div>
        <label className="field-label">Wavelength band</label>
        <div className="select">
          2.42–3.82 μm <span>Band group 4</span>
          <Icon name="chevron" />
        </div>
        <div className="range-head">
          <label>Magnitude range</label>
          <b>16.0 — 21.5</b>
        </div>
        <input type="range" min="12" max="24" defaultValue="20" />
        <div className="range-head">
          <label>Minimum confidence</label>
          <b>{confidence}%</b>
        </div>
        <input
          type="range"
          min="50"
          max="95"
          value={confidence}
          onChange={(e) => setConfidence(+e.target.value)}
        />
        <div className="range-head">
          <label>Motion threshold</label>
          <b>1.2″ / yr</b>
        </div>
        <input type="range" min="0" max="30" defaultValue="12" />
        <label className="toggle-row">
          <span>
            <b>Multi-epoch detections</b>
            <small>Require at least 3 observations</small>
          </span>
          <input type="checkbox" defaultChecked />
          <i />
        </label>
        <Button>
          Apply filters <span className="button-count">{filtered.length}</span>
        </Button>
      </Glass>
      <Glass className="candidate-panel panel">
        <div className="panel-title">
          <div>
            <small>LIVE RESULTS</small>
            <h3>{filtered.length} candidates</h3>
          </div>
          <span className="live-dot">Survey live</span>
        </div>
        <div className="search">
          <Icon name="search" />
          <input
            aria-label="Search candidates"
            placeholder="Search object ID"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="candidate-list">
          {filtered.length ? (
            filtered.map((c, i) => (
              <CandidateCard
                key={c.id}
                c={c}
                onClick={() => {
                  selectCandidate(i);
                  setScreen("detail");
                }}
              />
            ))
          ) : (
            <EmptyState />
          )}
        </div>
      </Glass>
      <Glass className="map-tools">
        <button aria-label="Zoom in">
          <Icon name="plus" />
        </button>
        <button aria-label="Zoom out">
          <Icon name="minus" />
        </button>
        <i />
        <button>
          <Icon name="layers" /> Layers
        </button>
        <button>IR composite</button>
      </Glass>
    </main>
  );
}

function Chart({ type = "spectrum" }: { type?: "spectrum" | "motion" }) {
  return (
    <div className={`chart ${type}`}>
      <div className="axis y">Flux density</div>
      <svg viewBox="0 0 640 210" preserveAspectRatio="none">
        <g className="gridlines">
          <path d="M0 40h640M0 90h640M0 140h640M0 190h640" />
        </g>
        {type === "spectrum" ? (
          <>
            <path
              className="chart-area"
              d="M0 170 C55 165 75 156 104 112 S148 56 182 130 S240 167 279 92 S328 38 357 119 S413 156 455 83 S508 104 537 62 S585 41 640 28 V210H0Z"
            />
            <path
              className="chart-line"
              d="M0 170 C55 165 75 156 104 112 S148 56 182 130 S240 167 279 92 S328 38 357 119 S413 156 455 83 S508 104 537 62 S585 41 640 28"
            />
            <circle cx="537" cy="62" r="5" />
          </>
        ) : (
          <>
            <path className="motion-path" d="M80 170 C170 150 240 131 320 112 S470 66 560 38" />
            {[80, 170, 245, 320, 395, 470, 560].map((x, i) => (
              <circle key={x} cx={x} cy={170 - i * 22} r="6" />
            ))}
          </>
        )}
      </svg>
      <div className="axis x">
        {type === "spectrum" ? "Wavelength (μm)" : "Observation epoch →"}
      </div>
    </div>
  );
}

function Detail({
  setScreen,
  candidate,
}: {
  setScreen: (s: Screen) => void;
  candidate: (typeof candidates)[0];
}) {
  const [flagged, setFlagged] = useState(false);
  return (
    <main className="content-screen">
      <section className="detail-head">
        <button className="back" onClick={() => setScreen("explore")}>
          ← Sky Explorer
        </button>
        <div className="title-line">
          <div>
            <span className="chip success">
              <Icon name="spark" size={12} /> High-priority candidate
            </span>
            <h1>{candidate.id}</h1>
            <p>SPHEREx moving source candidate · First detected 2025-04-18</p>
          </div>
          <div className="detail-actions">
            <Button variant="secondary" onClick={() => setFlagged(!flagged)}>
              <Icon name={flagged ? "check" : "flag"} />
              {flagged ? "Flagged" : "Flag candidate"}
            </Button>
            <Button variant="secondary" onClick={() => setScreen("timelapse")}>
              <Icon name="play" />
              Timelapse
            </Button>
            <Button variant="secondary" onClick={() => setScreen("compare")}>
              <Icon name="compare" />
              Compare
            </Button>
            <Button variant="secondary">
              <Icon name="export" />
              Export
            </Button>
          </div>
        </div>
      </section>
      <section className="epoch-strip">
        {["2025 · 04 · 18", "2025 · 07 · 22", "2025 · 10 · 26"].map((d, i) => (
          <Glass className="epoch" key={d}>
            <div style={{ backgroundImage: `url(${i === 1 ? nebulaImage : spaceImage})` }}>
              <span className={`epoch-target e${i}`} />
              <small>{d}</small>
            </div>
          </Glass>
        ))}
        <Glass className="motion-summary">
          <small>MEASURED MOTION</small>
          <strong>
            {candidate.motion}
            <sup>″ / yr</sup>
          </strong>
          <span>± 0.08 arcsec</span>
          <div className="motion-arrow">⟶</div>
        </Glass>
      </section>
      <section className="stat-grid">
        {[
          ["CONFIDENCE", `${candidate.confidence}%`, "+6.2%"],
          ["APPARENT MAG", candidate.mag.toFixed(2), "W1 band"],
          ["OBSERVATIONS", "7", "3 epochs"],
          ["DISTANCE EST.", "480 AU", "± 72 AU"],
        ].map((x) => (
          <Glass className="stat" key={x[0]}>
            <small>{x[0]}</small>
            <strong>{x[1]}</strong>
            <span>{x[2]}</span>
          </Glass>
        ))}
      </section>
      <section className="data-grid">
        <Glass className="chart-card wide">
          <div className="card-heading">
            <div>
              <small>SPECTRAL PROFILE</small>
              <h3>SPHEREx spectrum</h3>
            </div>
            <div className="legend">
              <i /> Observed <i /> Model
            </div>
          </div>
          <Chart />
        </Glass>
        <Glass className="confidence-card">
          <small>COMBINED SIGNAL</small>
          <div className="big-score">
            {candidate.confidence}
            <sup>%</sup>
          </div>
          <h3>Strong candidate</h3>
          <p>Evidence is consistent across motion, spectral shape, and source quality.</p>
          {[
            ["Motion signature", 96],
            ["Spectral match", 91],
            ["Source quality", 88],
          ].map((x) => (
            <div className="metric" key={x[0]}>
              <span>
                {x[0]} <b>{x[1]}%</b>
              </span>
              <i>
                <em style={{ width: `${x[1]}%` }} />
              </i>
            </div>
          ))}
          <Button onClick={() => setScreen("orbit")}>
            View predicted orbit <Icon name="arrow" />
          </Button>
        </Glass>
        <Glass className="chart-card motion-card">
          <div className="card-heading">
            <div>
              <small>ASTROMETRY</small>
              <h3>Motion track</h3>
            </div>
            <span className="chip">7 detections</span>
          </div>
          <Chart type="motion" />
        </Glass>
        <Glass className="parameters">
          <div className="card-heading">
            <div>
              <small>COORDINATES</small>
              <h3>Key parameters</h3>
            </div>
          </div>
          {[
            ["Right ascension", candidate.ra],
            ["Declination", candidate.dec],
            ["Galactic latitude", "−12.847°"],
            ["Ecliptic latitude", "+17.221°"],
            ["Parallax", "2.08 ± 0.31 mas"],
          ].map((x) => (
            <div className="parameter" key={x[0]}>
              <span>{x[0]}</span>
              <b>{x[1]}</b>
            </div>
          ))}
        </Glass>
      </section>
    </main>
  );
}

function OrbitView({
  setScreen,
  candidate,
}: {
  setScreen: (s: Screen) => void;
  candidate: (typeof candidates)[0];
}) {
  const [playing, setPlaying] = useState(false);
  const [year, setYear] = useState(2038);
  return (
    <main className="app-screen orbit-screen">
      <div className="orbit-viewport">
        <div className="orbit-stars" />
        <div className="solar">
          <span className="sun-3d" />
          {[1, 2, 3, 4, 5].map((i) => (
            <span key={i} className={`planet-orbit po-${i}`}>
              <i />
            </span>
          ))}
          <span className="predicted-orbit">
            <i />
            <b>{candidate.id}</b>
          </span>
        </div>
        <div className="view-label">
          <span>ORBIT SIMULATION</span>
          <b>{year}</b>
          <small>Heliocentric · 1 AU grid</small>
        </div>
      </div>
      <Glass className="orbit-panel panel">
        <div className="panel-title">
          <div>
            <small>PREDICTED ORBIT</small>
            <h3>{candidate.id}</h3>
          </div>
          <button className="icon-button" onClick={() => setScreen("detail")}>
            <Icon name="close" />
          </button>
        </div>
        {[
          ["Semi-major axis", "512 AU"],
          ["Eccentricity", "0.34"],
          ["Inclination", "17.8°"],
          ["Orbital period", "11,580 yr"],
          ["Perihelion", "338 AU"],
        ].map((x) => (
          <div className="parameter" key={x[0]}>
            <span>{x[0]}</span>
            <b>{x[1]}</b>
          </div>
        ))}
        <div className="confidence-note">
          <Icon name="spark" />
          <p>
            <b>94% trajectory fit</b>
            <br />
            Based on 7 astrometric detections
          </p>
        </div>
        <Button onClick={() => setScreen("compare")}>
          Compare candidate <Icon name="compare" />
        </Button>
      </Glass>
      <Glass className="timeline">
        <button className="play" onClick={() => setPlaying(!playing)}>
          <Icon name={playing ? "pause" : "play"} />
        </button>
        <span>2025</span>
        <input
          type="range"
          min="2025"
          max="2055"
          value={year}
          onChange={(e) => setYear(+e.target.value)}
        />
        <span>2055</span>
        <b>{year}</b>
      </Glass>
    </main>
  );
}

function Compare({ setScreen }: { setScreen: (s: Screen) => void }) {
  return (
    <main className="content-screen compare-screen">
      <div className="section-title">
        <small>CANDIDATE ANALYSIS</small>
        <h1>Compare signals</h1>
        <p>Review the strongest evidence side by side.</p>
      </div>
      <div className="compare-grid">
        {candidates.slice(0, 2).map((c, i) => (
          <div className="compare-col" key={c.id}>
            <CandidateCard c={c} selected={!i} onClick={() => {}} />
            <Glass className="compare-chart">
              <div className="card-heading">
                <h3>Spectral profile</h3>
                <span className="chip">{c.confidence}% match</span>
              </div>
              <Chart />
            </Glass>
            {[
              ["Proper motion", `${c.motion}″ / yr`],
              ["Apparent magnitude", c.mag.toFixed(2)],
              ["Distance estimate", i ? "392 AU" : "480 AU"],
              ["Detection quality", i ? "Good" : "Excellent"],
            ].map((x) => (
              <Glass className="compare-row" key={x[0]}>
                <span>{x[0]}</span>
                <b>{x[1]}</b>
              </Glass>
            ))}
            {!i && (
              <Button onClick={() => setScreen("detail")}>
                Open candidate <Icon name="arrow" />
              </Button>
            )}
          </div>
        ))}
      </div>
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
          PARALLAX turns SPHEREx all-sky observations into an accessible search for faint,
          slow-moving worlds.
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
            <h2>From raw light to candidate.</h2>
            <div className="pipeline">
              {[
                "Ingest survey epochs",
                "Cross-match sources",
                "Measure motion",
                "Score candidates",
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
              Our prototype combines simulated SPHEREx Level 2 spectra with reference astrometry
              from Gaia DR3 and infrared photometry from NEOWISE. Orbital estimates are exploratory,
              not confirmed discoveries.
            </p>
            <div className="source-chips">
              <span>NASA SPHEREx</span>
              <span>Gaia DR3</span>
              <span>NEOWISE</span>
              <span>JPL Horizons</span>
            </div>
          </div>
        </section>
      </Glass>
    </main>
  );
}

function EmptyState() {
  return (
    <div className="empty">
      <div>
        <Icon name="search" />
      </div>
      <b>No signals in this view</b>
      <p>Lower the confidence threshold to reveal more candidates.</p>
    </div>
  );
}

function MobileNav({ screen, setScreen }: { screen: Screen; setScreen: (s: Screen) => void }) {
  const items: [Screen, IconName, string][] = [
    ["home", "spark", "Home"],
    ["explore", "grid", "Explore"],
    ["timelapse", "play", "Timelapse"],
    ["orbit", "orbit", "Orbit"],
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

export default function App() {
  const [screen, setScreen] = useState<Screen>("home");
  const [selected, setSelected] = useState(0);
  const navigate = (s: Screen) => {
    setScreen(s);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  return (
    <div className="app">
      <Background />
      <Header screen={screen} setScreen={navigate} />
      {screen === "home" && <Home setScreen={navigate} />}{" "}
      {screen === "explore" && <Explorer setScreen={navigate} selectCandidate={setSelected} />}{" "}
      {screen === "detail" && <Detail setScreen={navigate} candidate={candidates[selected]} />}{" "}
      {screen === "timelapse" && (
        <Timelapse
          title={candidates[selected].id}
          backdrop={spaceImage}
          onBack={() => navigate("detail")}
        />
      )}
      {screen === "orbit" && <OrbitView setScreen={navigate} candidate={candidates[selected]} />}{" "}
      {screen === "compare" && <Compare setScreen={navigate} />} {screen === "about" && <About />}
      <MobileNav screen={screen} setScreen={navigate} />
    </div>
  );
}
