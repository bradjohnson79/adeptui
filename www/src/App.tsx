import { About, Audience, Faq, FinalCta, Footer, LocalApi, Platform } from "./components/Close";
import { DownloadSection } from "./components/DownloadAdeptUI";
import { Hero } from "./components/Hero";
import { Navigation } from "./components/Navigation";
import { FilmStill } from "./components/ProductFrame";
import { Continuity, Magi, Models, Systems, Timeline } from "./components/Production";
import { CoDirector, Storyboard, Why, Workflow, Workspace } from "./components/Story";
import { film } from "./content";

export function App() {
  return (
    <>
      <a className="skip" href="#ai-filmmaking">
        Skip to content
      </a>
      <Navigation />
      <main>
        <Hero />
        <Why />
        <FilmStill
          src={film.director.src}
          alt={film.director.alt}
          width={1280}
          height={720}
          caption={film.director.caption}
        />
        <Workspace />
        <CoDirector />
        <Storyboard />
        <Workflow />
        <Systems />
        <Continuity />
        <Timeline />
        <FilmStill
          src={film.camera.src}
          alt={film.camera.alt}
          width={1280}
          height={720}
          caption={film.camera.caption}
        />
        <Magi />
        <Models />
        <DownloadSection />
        <LocalApi />
        <About />
        <Audience />
        <Platform />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </>
  );
}
