import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import "./index.css";
import App from "./App.jsx";
import { AuthProvider, useAuth } from "./auth/AuthContext.jsx";
import { LanguageProvider } from "./i18n/useT.js";

// Fix Leaflet's default marker asset paths under bundlers.
L.Marker.prototype.options.icon = L.icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

function LangBridge({ children }) {
  // keep the UI language in sync with the signed-in farmer's preference
  const { user } = useAuth();
  return <LanguageProvider initial={user?.default_language}>{children}</LanguageProvider>;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <LangBridge>
          <App />
        </LangBridge>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
