import { Footer } from "./Close";
import { ContactForm } from "./ContactForm";
import { Navigation } from "./Navigation";

export function ContactPage() {
  return (
    <>
      <a className="skip" href="#contact">
        Skip to content
      </a>
      <Navigation />
      <main>
        <section className="chapter contact" id="contact" aria-labelledby="contact-title">
          <div className="chapter__inner">
            <p className="eyebrow">Contact</p>
            <h1 id="contact-title">Contact Adept UI</h1>
            <p className="lede">Questions, bug reports, and media requests.</p>
            <ContactForm />
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
