import { WelcomeGreeting } from "@/components/dashboard/WelcomeGreeting";

export function WelcomeSection() {
  return (
    <section className="home-welcome">
      <h1 className="home-welcome-title">
        <span className="home-welcome-hello">
          <WelcomeGreeting />
        </span>
        <span className="home-welcome-question">
          What would you like to learn today?
        </span>
      </h1>
      <p className="home-welcome-lead">
        Pick up where you left off, or start something new.
      </p>
    </section>
  );
}
