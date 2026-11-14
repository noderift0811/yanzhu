import React from "react";
import ReactDOM from "react-dom/client";
import "antd/dist/reset.css";
import App from "./App.jsx";
import "./styles/theme.css";
import "./styles/skeletons.css";
import "./styles/skeletons-extra.css";
import "./styles/picker.css";
import "./styles/agent.css";
import "./styles/scene.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
