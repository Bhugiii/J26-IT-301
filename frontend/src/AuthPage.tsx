import { useState, type FormEvent } from "react";
import "./landing.css";
import "./auth.css";

export type AuthMode = "login" | "register";

export interface SignupProfileFields {
  name: string;
  budget: string;
  tripDuration: string;
  startingLocation: string;
  interests: string;
}

interface AuthPageProps {
  mode: AuthMode;
  email: string;
  password: string;
  profile: SignupProfileFields;
  loading: boolean;
  message: string;
  guestProfileNote: string | null;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onProfileChange: (field: keyof SignupProfileFields, value: string) => void;
  onSubmit: () => void;
  onModeChange: (mode: AuthMode) => void;
  onBack: () => void;
  onContinueAsGuest: () => void;
}

const HERO_PHOTO =
  "https://images.unsplash.com/photo-1566296314736-6eaac1ca0cb9?auto=format&fit=crop&w=1400&q=80";

function AuthPage({
  mode,
  email,
  password,
  profile,
  loading,
  message,
  guestProfileNote,
  onEmailChange,
  onPasswordChange,
  onProfileChange,
  onSubmit,
  onModeChange,
  onBack,
  onContinueAsGuest,
}: AuthPageProps) {
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [mismatch, setMismatch] = useState(false);
  const registering = mode === "register";

  function switchMode(next: AuthMode) {
    setConfirmPassword("");
    setMismatch(false);
    onModeChange(next);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (registering && password !== confirmPassword) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    onSubmit();
  }

  return (
    <div className="auth-page">
      <aside className="auth-visual" style={{ backgroundImage: `url(${HERO_PHOTO})` }}>
        <div className="auth-visual-inner">
          <button className="landing-brand auth-brand" onClick={onBack}>
            <img src="/travelmind-logo.svg" alt="" />
            <strong>TravelMind</strong>
          </button>

          <div className="auth-visual-copy">
            <h2>Sri Lanka, your way.</h2>
            <p>Keep your traveller profile, saved places and recommendations together, ready whenever you come back.</p>
            <ul>
              <li>Recommendations ranked for your interests and budget</li>
              <li>The reasons behind every suggestion</li>
              <li>A day-by-day plan built from your shortlist</li>
            </ul>
          </div>
        </div>
      </aside>

      <main className="auth-panel">
        <button className="auth-back" onClick={onBack}>← Back</button>

        <div className="auth-card">
          <span className="landing-eyebrow">{registering ? "NEW TO TRAVELMIND" : "WELCOME BACK"}</span>
          <h1>{registering ? "Create your account" : "Sign in to your account"}</h1>
          <p className="auth-lead">
            {registering
              ? "Set up your account and traveller profile together. It takes about a minute."
              : "Sign in to open your traveller profiles and saved places."}
          </p>

          <div className="auth-tabs" role="tablist" aria-label="Account">
            <button role="tab" aria-selected={!registering} className={registering ? "" : "active"} onClick={() => switchMode("login")}>
              Sign in
            </button>
            <button role="tab" aria-selected={registering} className={registering ? "active" : ""} onClick={() => switchMode("register")}>
              Create account
            </button>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <label className="auth-field">
              <span>Email</span>
              <input type="email" autoComplete="email" required maxLength={254} value={email} onChange={(event) => onEmailChange(event.target.value)} placeholder="you@example.com" />
            </label>

            <label className="auth-field">
              <span>Password</span>
              <div className="auth-password">
                <input
                  type={showPassword ? "text" : "password"}
                  autoComplete={registering ? "new-password" : "current-password"}
                  required
                  minLength={registering ? 10 : 1}
                  maxLength={128}
                  value={password}
                  onChange={(event) => onPasswordChange(event.target.value)}
                  placeholder={registering ? "At least 10 characters" : "Your password"}
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)} aria-pressed={showPassword}>
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </label>

            {registering && (
              <>
                <label className="auth-field">
                  <span>Confirm password</span>
                  <input
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    required
                    maxLength={128}
                    value={confirmPassword}
                    onChange={(event) => { setConfirmPassword(event.target.value); setMismatch(false); }}
                    placeholder="Type the password again"
                  />
                </label>

                <fieldset className="auth-profile">
                  <legend>About your trips</legend>
                  <p>These set up your first recommendations. You can change them any time.</p>

                  <label className="auth-field">
                    <span>Your name</span>
                    <input required maxLength={80} autoComplete="name" value={profile.name} onChange={(event) => onProfileChange("name", event.target.value)} placeholder="e.g. Nimali" />
                  </label>

                  <div className="auth-row">
                    <label className="auth-field">
                      <span>Daily budget (LKR)</span>
                      <input type="number" min="1" required value={profile.budget} onChange={(event) => onProfileChange("budget", event.target.value)} />
                    </label>
                    <label className="auth-field">
                      <span>Trip length (days)</span>
                      <input type="number" min="1" max="30" required value={profile.tripDuration} onChange={(event) => onProfileChange("tripDuration", event.target.value)} />
                    </label>
                  </div>

                  <label className="auth-field">
                    <span>Starting location</span>
                    <input required value={profile.startingLocation} onChange={(event) => onProfileChange("startingLocation", event.target.value)} placeholder="Colombo" />
                  </label>

                  <label className="auth-field">
                    <span>Interests</span>
                    <input required value={profile.interests} onChange={(event) => onProfileChange("interests", event.target.value)} placeholder="Nature, hiking, wildlife" />
                  </label>
                </fieldset>

                {guestProfileNote && <p className="auth-note">{guestProfileNote}</p>}
              </>
            )}

            {mismatch && <p className="auth-message error" role="alert">The two passwords do not match.</p>}
            {message && !mismatch && <p className="auth-message" role="status">{message}</p>}

            <button className="landing-button solid large auth-submit" type="submit" disabled={loading}>
              {loading ? "Please wait…" : registering ? "Create account" : "Sign in"}
            </button>
          </form>

          <p className="auth-switch">
            {registering ? "Already have an account?" : "New to TravelMind?"}{" "}
            <button onClick={() => switchMode(registering ? "login" : "register")}>
              {registering ? "Sign in" : "Create an account"}
            </button>
          </p>

          <div className="auth-divider"><span>or</span></div>

          <button className="landing-button outline auth-guest" onClick={onContinueAsGuest}>
            Continue as a guest
          </button>

          <p className="auth-small">
            This research prototype stores account data on the project server. Password reset and
            email verification are not available yet, so keep your password somewhere safe.
          </p>
        </div>
      </main>
    </div>
  );
}

export default AuthPage;
