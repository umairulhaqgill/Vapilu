import { useState } from "react";
import { UserPlus } from "lucide-react";

interface Props {
  onSignup: () => void;
  onGoToLogin: () => void;
}

export default function Signup({ onSignup, onGoToLogin }: Props) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    // Dummy auth - see Login.tsx.
    onSignup();
  };

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand">
          <span className="sidebar-brand-mark">V</span>
          <span>Vapilu</span>
        </div>
        <h2>Create an account</h2>
        <p className="muted auth-subtitle">Set up super-admin access to the Flow Builder.</p>

        {error && <p className="error">{error}</p>}

        <label>Name</label>
        <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />

        <label>Email</label>
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@vapilu.com" />

        <label>Password</label>
        <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />

        <label>Confirm password</label>
        <input type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="••••••••" />

        <button type="submit" className="primary auth-submit">
          <UserPlus size={15} />
          Create account
        </button>

        <p className="muted auth-switch">
          Already have an account?{" "}
          <button type="button" className="link-button" onClick={onGoToLogin}>Sign in</button>
        </p>

        <p className="auth-note">Demo only - no account is actually created, nothing is sent anywhere.</p>
      </form>
    </div>
  );
}
