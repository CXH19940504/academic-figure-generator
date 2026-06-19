import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import { Projects } from "./pages/Projects";
import { ProjectWorkspace } from "./pages/ProjectWorkspace";
import { ColorSchemes } from "./pages/ColorSchemes";
import { Settings } from "./pages/Settings";
import { Generate } from "./pages/Generate";
import { Outline } from "./pages/Outline";

function App() {
  return (
    <Router>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/:id" element={<ProjectWorkspace />} />
          <Route path="/color-schemes" element={<ColorSchemes />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/generate" element={<Generate />} />
          <Route path="/outline" element={<Outline />} />
          <Route path="/outline/:projectId" element={<Outline />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
