import { coDirector, shots, storyboard, why, workflow, workspace } from "../content";
import { ProductFrame } from "./ProductFrame";
import { Chapter, SectionHeading } from "./ui";

const fragments = [
  { label: "IMG", x: 46, y: 11 },
  { label: "VOICE", x: 16, y: 31 },
  { label: "VID", x: 76, y: 27 },
  { label: "FILES", x: 18, y: 52 },
  { label: "MODEL", x: 74, y: 50 },
  { label: "EDIT", x: 44, y: 65 },
  { label: "TIMELINE", x: 22, y: 84 },
  { label: "PROMPT", x: 72, y: 82 },
] as const;

const compactFragments = [
  { label: "IMG", x: 18, y: 28 },
  { label: "VOICE", x: 46, y: 62 },
  { label: "VID", x: 78, y: 24 },
  { label: "FILES", x: 28, y: 78 },
] as const;

function FragmentedTools() {
  return (
    <div className="fragment" aria-hidden="true">
      <svg className="fragment__field" viewBox="0 0 100 100" preserveAspectRatio="none">
        <ellipse className="fragment__glow" cx="30" cy="72" rx="18" ry="14" />
        <ellipse className="fragment__glow fragment__glow--cool" cx="74" cy="38" rx="14" ry="11" />
        <path className="fragment__trace" d="M46 16 L46 23" />
        <path className="fragment__signal" d="M46 16 L46 23" />
        <path className="fragment__trace" d="M45 27 L42 31" />
        <path className="fragment__trace" d="M54 10 Q62 7 68 14" />
        <path className="fragment__trace" d="M71 17 L73 19" />
        <path className="fragment__trace" d="M24 31 L33 34" />
        <path className="fragment__trace" d="M36 36 L39 37" />
        <path className="fragment__trace" d="M12 27 Q7 35 13 41" />
        <path className="fragment__trace" d="M18 46 L15 40" />
        <path className="fragment__trace" d="M26 54 L35 59" />
        <path className="fragment__trace" d="M39 62 L41 63" />
        <path className="fragment__trace" d="M76 33 L75 41" />
        <path className="fragment__trace" d="M74 44 L73 46" />
        <path className="fragment__trace" d="M66 51 L57 55" />
        <path className="fragment__trace" d="M82 44 Q88 50 80 56" />
        <path className="fragment__trace" d="M40 70 L33 76" />
        <path className="fragment__trace" d="M28 80 L26 82" />
        <path className="fragment__trace" d="M50 70 L58 76" />
        <path className="fragment__trace" d="M63 79 L66 80" />
        <path className="fragment__trace" d="M30 84 L38 83" />
        <path className="fragment__trace" d="M64 83 L56 85" />
        <circle className="fragment__dot" cx="43" cy="22" r="0.55" />
        <circle className="fragment__dot" cx="39" cy="43" r="0.45" />
        <circle className="fragment__dot" cx="55" cy="46" r="0.5" />
        <circle className="fragment__dot" cx="31" cy="70" r="0.4" />
        <circle className="fragment__dot" cx="62" cy="66" r="0.45" />
        <circle className="fragment__dot" cx="50" cy="40" r="0.35" />
      </svg>
      {fragments.map((node) => (
        <span key={node.label} className="fragment__node" style={{ left: `${node.x}%`, top: `${node.y}%` }}>
          {node.label}
        </span>
      ))}
      <div className="fragment__compact">
        <svg viewBox="0 0 100 40" preserveAspectRatio="none">
          <path className="fragment__trace" d="M22 12 L30 16" />
          <path className="fragment__trace" d="M34 18 L37 19" />
          <path className="fragment__trace" d="M70 12 L62 16" />
          <path className="fragment__trace" d="M24 28 L32 26" />
          <path className="fragment__trace" d="M52 26 L58 22" />
          <circle className="fragment__dot" cx="42" cy="18" r="0.7" />
          <circle className="fragment__dot" cx="48" cy="30" r="0.6" />
        </svg>
        {compactFragments.map((node) => (
          <span key={node.label} className="fragment__node" style={{ left: `${node.x}%`, top: `${node.y}%` }}>
            {node.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export function Why() {
  return (
    <Chapter id="why" labelledBy="why-title">
      <SectionHeading id="why-title" eyebrow={why.eyebrow} title={why.title} lede={why.lede} />
      <div className="compare">
        <article className="compare__before">
          <p className="eyebrow">Before</p>
          <h3>{why.beforeTitle}</h3>
          <ul className="chips">
            {why.before.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <FragmentedTools />
        </article>
        <article className="compare__after">
          <p className="eyebrow">After</p>
          <h3>{why.afterTitle}</h3>
          <ul className="stack">
            {why.after.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </div>
    </Chapter>
  );
}

export function Workspace() {
  return (
    <Chapter id="workspace" labelledBy="workspace-title" wide>
      <SectionHeading id="workspace-title" eyebrow={workspace.eyebrow} title={workspace.title} lede={workspace.lede} />
      <div className="orbit-wrap">
        <ul className="orbit" aria-label="Adept UI connected to the production">
          <li className="orbit__core">
            <img src="/brand/adept-ui-emblem.webp" alt="" width={640} height={640} />
            <span>{workspace.core}</span>
          </li>
          {workspace.nodes.map((node, index) => (
            <li key={node} className="orbit__node" style={{ ["--i" as string]: index }}>
              {node}
            </li>
          ))}
        </ul>
      </div>
    </Chapter>
  );
}

export function CoDirector() {
  return (
    <Chapter id="co-director" labelledBy="codirector-title" wide>
      <div className="split">
        <ProductFrame
          src={shots.codirector.src}
          alt={shots.codirector.alt}
          width={894}
          height={843}
          caption={coDirector.caption}
        />
        <div>
          <SectionHeading
            id="codirector-title"
            eyebrow={coDirector.eyebrow}
            title={coDirector.title}
            lede={coDirector.lede}
          />
          <p className="lede">{coDirector.body}</p>
          <ul className="relations" aria-label="Co-Director works across these parts of Adept UI">
            {coDirector.relations.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        </div>
      </div>
      <ol className="stages">
        {coDirector.stages.map((stage, index) => (
          <li key={stage.title} className={index % 2 ? "stage stage--flip" : "stage"}>
            <span className="stage__index">{stage.index}</span>
            <div className="stage__copy">
              <h3>{stage.title}</h3>
              <p>{stage.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </Chapter>
  );
}

export function Storyboard() {
  return (
    <Chapter id="storyboard" labelledBy="storyboard-title" wide>
      <SectionHeading id="storyboard-title" eyebrow={storyboard.eyebrow} title={storyboard.title} lede={storyboard.lede} />
      <ProductFrame
        className="shot--stage"
        src={shots.storyboard.src}
        alt={shots.storyboard.alt}
        width={894}
        height={843}
        caption={storyboard.caption}
      />
    </Chapter>
  );
}

export function Workflow() {
  return (
    <Chapter id="workflow" labelledBy="workflow-title" wide>
      <SectionHeading id="workflow-title" eyebrow={workflow.eyebrow} title={workflow.title} lede={workflow.lede} />
      <ol className="flow">
        {workflow.steps.map((step) => (
          <li key={step.index}>
            <span className="flow__index">{step.index}</span>
            <h3>{step.title}</h3>
            <ul>
              {step.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </Chapter>
  );
}
