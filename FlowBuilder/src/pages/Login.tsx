import { useState } from "react";
import { LogIn } from "lucide-react";

interface Props {
  onLogin: () => void;
  onGoToSignup: () => void;
}

export default function Login({ onLogin, onGoToSignup }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    // Dummy auth - no backend call. Real per-user auth with tenant scoping
    // has to land server-side before this could ever be real (see
    // CLAUDE.md "Known gaps that matter") - this is a prototype of the
    // shell only.
    onLogin();
  };

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand">
          <span className="sidebar-brand-mark">V</span>
          <span>Vapilu</span>
        </div>
        <h2>Sign in</h2>
        <p className="muted auth-subtitle">Super-admin access to the Flow Builder.</p>

        <label>Email</label>
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@vapilu.com" />

        <label>Password</label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
        />

        <button type="submit" className="primary auth-submit">
          <LogIn size={15} />
          Sign in
        </button>

        <p className="muted auth-switch">
          Don't have an account?{" "}
          <button type="button" className="link-button" onClick={onGoToSignup}>Sign up</button>
        </p>

        <p className="auth-note">Demo only - no credentials are checked, nothing is sent anywhere.</p>
      </form>
    </div>
  );
}
