import { useId, useState, type FormEvent } from "react";
import { categoryFromSearch, contactCategories, contactFailure, contactPrivacy, type ContactCategoryId } from "../contact";

type Fields = {
  name: string;
  email: string;
  category: ContactCategoryId;
  subject: string;
  message: string;
  version: string;
  os: string;
  company: string;
};

const empty: Fields = {
  name: "",
  email: "",
  category: "general",
  subject: "",
  message: "",
  version: "",
  os: "",
  company: "",
};

function initialFields(): Fields {
  return { ...empty, category: categoryFromSearch(window.location.search) };
}

export function ContactForm() {
  const [fields, setFields] = useState<Fields>(initialFields);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const helpId = useId();
  const errorId = useId();
  const statusId = useId();
  const category = contactCategories.find((item) => item.id === fields.category) ?? contactCategories[0];

  function update<Key extends keyof Fields>(key: Key, value: Fields[Key]) {
    setFields((current) => ({ ...current, [key]: value }));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const response = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: fields.name,
          email: fields.email,
          category: fields.category,
          subject: fields.subject,
          message: fields.message,
          version: fields.category === "bug" ? fields.version : "",
          os: fields.category === "bug" ? fields.os : "",
          company: fields.company,
        }),
      });
      let payload: { message?: string } = {};
      try {
        payload = (await response.json()) as { message?: string };
      } catch {
        payload = {};
      }
      const message = payload.message || contactFailure;
      if (!response.ok) {
        setError(message);
        return;
      }
      setStatus(message);
      setFields(empty);
    } catch {
      setError(contactFailure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="contact-form" onSubmit={onSubmit} noValidate>
      <label>
        Name
        <input
          name="name"
          autoComplete="name"
          value={fields.name}
          maxLength={80}
          required
          aria-invalid={error === "Enter your name." || error === "Enter a shorter name."}
          onChange={(event) => update("name", event.target.value)}
        />
      </label>
      <label>
        Email
        <input
          name="email"
          type="email"
          autoComplete="email"
          value={fields.email}
          maxLength={120}
          required
          aria-invalid={error === "Enter a valid email address."}
          onChange={(event) => update("email", event.target.value)}
        />
      </label>
      <label>
        Category
        <select
          name="category"
          value={fields.category}
          aria-describedby={helpId}
          onChange={(event) => update("category", event.target.value as ContactCategoryId)}
        >
          {contactCategories.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <p className="contact-help" id={helpId}>
        {category.help}
      </p>
      {fields.category === "bug" ? (
        <>
          <label>
            Adept UI version
            <input
              name="version"
              value={fields.version}
              maxLength={60}
              placeholder="Optional"
              onChange={(event) => update("version", event.target.value)}
            />
          </label>
          <label>
            Operating system
            <input
              name="os"
              value={fields.os}
              maxLength={60}
              placeholder="Optional"
              onChange={(event) => update("os", event.target.value)}
            />
          </label>
        </>
      ) : null}
      <label>
        Subject
        <input
          name="subject"
          value={fields.subject}
          maxLength={140}
          required
          aria-invalid={error === "Enter a subject." || error === "Enter a shorter subject."}
          onChange={(event) => update("subject", event.target.value)}
        />
      </label>
      <label>
        Message
        <textarea
          name="message"
          value={fields.message}
          maxLength={4000}
          required
          rows={7}
          aria-invalid={error === "Enter a message." || error === "Enter a shorter message."}
          onChange={(event) => update("message", event.target.value)}
        />
      </label>
      <div className="contact-hp" aria-hidden="true">
        <label>
          Company
          <input
            name="company"
            tabIndex={-1}
            autoComplete="off"
            value={fields.company}
            onChange={(event) => update("company", event.target.value)}
          />
        </label>
      </div>
      <p className="contact-privacy">{contactPrivacy}</p>
      <button className="btn btn--primary" type="submit" disabled={busy}>
        {busy ? "Sending…" : "Send Message"}
      </button>
      <p className="contact-error" id={errorId} role="alert">
        {error}
      </p>
      <p className="contact-status" id={statusId} role="status">
        {status}
      </p>
    </form>
  );
}
