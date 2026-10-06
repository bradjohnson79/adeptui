import { Button } from "../../ui";
import { PanelHeading } from "../../HelpTip";

export function AutoPrevizPanel({
  prompt,
  onPrompt,
  plan,
  onDraft,
  onApprove,
}: {
  prompt: string;
  onPrompt: (value: string) => void;
  plan: { planId: string; shots: Array<{ name: string; focusKind: string }> } | null;
  onDraft: () => void;
  onApprove: () => void;
}) {
  return (
    <section className="panel" data-testid="posecraft-auto-previz">
      <PanelHeading title="Auto Previz" tip="Co-Director drafts a simple shot plan. Nothing is built until you approve." />
      <label className="field">
        <span>What should happen</span>
        <input value={prompt} onChange={(event) => onPrompt(event.target.value)} data-testid="posecraft-auto-previz-prompt" />
      </label>
      <div className="row">
        <Button variant="secondary" onClick={onDraft} data-testid="posecraft-auto-previz-plan">Draft plan</Button>
        <Button variant="primary" onClick={onApprove} disabled={!plan} data-testid="posecraft-auto-previz-approve">Approve and build</Button>
      </div>
      {plan ? (
        <ol data-testid="posecraft-auto-previz-shots">
          {plan.shots.map((shot) => (
            <li key={shot.name}>{shot.name} · {shot.focusKind}</li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
