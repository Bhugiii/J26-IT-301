import "./landing.css";

export type LandingTarget =
  | "dashboard"
  | "recommendations"
  | "itinerary"
  | "crowd"
  | "weather"
  | "assistant";

interface LandingPageProps {
  signedInEmail: string | null;
  onEnter: (target: LandingTarget) => void;
  onSignIn: () => void;
  onCreateAccount: () => void;
}

const photo = (id: string, width: number) =>
  `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${width}&q=80`;

const components = [
  {
    number: "01",
    title: "Recommendations that explain themselves",
    text: "Ranked destinations matched to your interests, budget, pace and preferred crowd level, each with the reasons behind its score.",
    live: true,
  },
  {
    number: "02",
    title: "Geo-spatial tourism intelligence",
    text: "Maps of where visitors concentrate and which areas remain under-visited, to help spread tourism beyond the usual hotspots.",
    live: false,
  },
  {
    number: "03",
    title: "Promise versus reality index",
    text: "A trust signal that compares how a place is advertised with what visitors report about food, service, cleanliness and the overall experience.",
    live: false,
  },
  {
    number: "04",
    title: "Traveller behaviour segments",
    text: "Groups of travellers discovered from how people actually travel: how long they stay, where they go, what they do and how they spend.",
    live: false,
  },
];

const steps = [
  {
    title: "Tell us how you travel",
    text: "Set your interests, daily budget, trip length, pace and how busy you like a place to be.",
  },
  {
    title: "See places ranked for you",
    text: "Every destination shows its match score and a breakdown of what raised or lowered it.",
  },
  {
    title: "Turn the shortlist into a plan",
    text: "Save the places you like and lay them out day by day in the itinerary planner.",
  },
];

const features: { target: LandingTarget; title: string; text: string }[] = [
  { target: "recommendations", title: "Recommendations", text: "Your top destinations, with filters, a map view and what-if scenarios." },
  { target: "itinerary", title: "Itinerary planner", text: "A day-by-day plan built from your ranked places and travel pace." },
  { target: "crowd", title: "Crowd prediction", text: "Predicted crowd levels, so you can pick quieter alternatives." },
  { target: "weather", title: "Weather intelligence", text: "How well each destination suits the weather you prefer." },
  { target: "assistant", title: "Explainable AI chat", text: "Ask why a place was recommended and see the evidence behind the answer." },
  { target: "dashboard", title: "Your dashboard", text: "A summary of your matches, preferences and next steps in one place." },
];

const gallery = [
  { id: "photo-1612862862126-865765df2ded", caption: "Sigiriya rock fortress" },
  { id: "photo-1566296314736-6eaac1ca0cb9", caption: "Nine Arches Bridge, Ella" },
  { id: "photo-1519566335946-e6f65f0f4fdf", caption: "Stilt fishermen on the coast" },
  { id: "photo-1533484482814-3fe2d922be89", caption: "Elephants at the river" },
];

function LandingPage({ signedInEmail, onEnter, onSignIn, onCreateAccount }: LandingPageProps) {
  return (
    <div className="landing">
      <header className="landing-nav">
        <a className="landing-brand" href="#top">
          <img src="/travelmind-logo.svg" alt="" />
          <strong><span className="brand-travel">Travel</span><span className="brand-mind">Mind</span></strong>
        </a>

        <nav className="landing-links" aria-label="Sections">
          <a href="#components">What it does</a>
          <a href="#how">How it works</a>
          <a href="#features">Features</a>
          <a href="#research">Research</a>
        </nav>

        <div className="landing-nav-actions">
          {signedInEmail ? (
            <button className="landing-button solid" onClick={() => onEnter("dashboard")}>Open dashboard</button>
          ) : (
            <>
              <button className="landing-button ghost" onClick={onSignIn}>Sign in</button>
              <button className="landing-button solid" onClick={onCreateAccount}>Create account</button>
            </>
          )}
        </div>
      </header>

      <main id="top">
        <section
          className="landing-hero"
          style={{ backgroundImage: `url(${photo("photo-1612862862126-865765df2ded", 2000)})` }}
        >
          <div className="landing-hero-inner">
            <span className="landing-eyebrow">SMART TOURISM FOR SRI LANKA</span>
            <h1>Find the Sri Lanka that fits the way you travel.</h1>
            <p>
              TravelMind ranks destinations against your interests, budget and pace, weighs crowds
              and weather, and tells you why each place made your list.
            </p>

            <div className="landing-hero-actions">
              <button className="landing-button solid large" onClick={() => onEnter("recommendations")}>
                Explore destinations
              </button>
              {signedInEmail ? (
                <button className="landing-button glass large" onClick={() => onEnter("dashboard")}>
                  Go to my dashboard
                </button>
              ) : (
                <button className="landing-button glass large" onClick={onCreateAccount}>
                  Create a free account
                </button>
              )}
            </div>

            <ul className="landing-hero-points">
              <li>Explains every recommendation</li>
              <li>Weighs crowds, weather and budget</li>
              <li>No account needed to explore</li>
            </ul>
          </div>
        </section>

        <section className="landing-section" id="components">
          <div className="landing-heading">
            <span className="landing-eyebrow">WHAT IT DOES</span>
            <h2>Four kinds of tourism intelligence, one platform</h2>
            <p>TravelMind brings together four research components. One is live in this prototype and three are being built.</p>
          </div>

          <div className="landing-components">
            {components.map((component) => (
              <article className="landing-component" key={component.number}>
                <div className="landing-component-top">
                  <span className="landing-component-number">{component.number}</span>
                  <span className={`landing-status ${component.live ? "live" : "building"}`}>
                    {component.live ? "Live in this prototype" : "In development"}
                  </span>
                </div>
                <h3>{component.title}</h3>
                <p>{component.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-section tinted" id="how">
          <div className="landing-heading">
            <span className="landing-eyebrow">HOW IT WORKS</span>
            <h2>From preferences to a plan in three steps</h2>
          </div>

          <ol className="landing-steps">
            {steps.map((step, index) => (
              <li key={step.title}>
                <span className="landing-step-number">{index + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="landing-gallery" aria-label="Places in Sri Lanka">
          {gallery.map((item) => (
            <figure key={item.id}>
              <img src={photo(item.id, 700)} alt={item.caption} loading="lazy" />
              <figcaption>{item.caption}</figcaption>
            </figure>
          ))}
        </section>

        <section className="landing-section" id="features">
          <div className="landing-heading">
            <span className="landing-eyebrow">WHAT YOU CAN DO TODAY</span>
            <h2>Everything in the prototype is open to try</h2>
          </div>

          <div className="landing-features">
            {features.map((feature) => (
              <button className="landing-feature" key={feature.title} onClick={() => onEnter(feature.target)}>
                <strong>{feature.title}</strong>
                <span>{feature.text}</span>
                <em aria-hidden="true">Open →</em>
              </button>
            ))}
          </div>
        </section>

        <section className="landing-section tinted" id="research">
          <div className="landing-research">
            <div>
              <span className="landing-eyebrow">THE RESEARCH</span>
              <h2>A final-year research project at SLIIT</h2>
              <p>
                TravelMind is project J26-IT-301 of the IT4010 Research Project module, built by four
                undergraduates in the Department of Information Technology at the Sri Lanka Institute
                of Information Technology, within the Centre of Excellence for AI research group.
              </p>
              <p>
                It asks whether demand forecasting, spatial analytics, review analysis and behaviour
                segmentation can work together to make travel in Sri Lanka more personal and more
                evenly spread across the island.
              </p>
            </div>

            <aside className="landing-note">
              <strong>This is a research prototype</strong>
              <p>
                Some destination details, including costs, crowd levels and weather suitability, are
                research estimates and are not live data. Check opening hours, prices and conditions
                with official sources before you travel.
              </p>
            </aside>
          </div>
        </section>

        <section className="landing-cta">
          <h2>Ready to see what fits you?</h2>
          <p>Explore as a guest, or create an account to keep your traveller profile and saved places.</p>
          <div className="landing-hero-actions">
            <button className="landing-button solid large" onClick={() => onEnter("recommendations")}>
              Explore destinations
            </button>
            {!signedInEmail && (
              <button className="landing-button outline large" onClick={onSignIn}>
                Sign in
              </button>
            )}
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <span>TravelMind · Sri Lanka, your way.</span>
        <span>IT4010 Research Project · J26-IT-301 · SLIIT</span>
      </footer>
    </div>
  );
}

export default LandingPage;
