// Dashboard map + filter helpers. Leaflet is loaded from cdnjs in base.html.
(function () {
  const KIND_COLORS = { teardown: "#D0521A", new_house: "#E07B3C", multiplex: "#B03A8C", garden_suite: "#2F8F5B", major_addition: "#C99A1B", pool: "#2A8FBD", underpinning: "#7A7A7A", second_suite: "#9C9C9C", new_building: "#5B4BB5" };
  const CAT_COLORS = { restaurant: "#137F68", bar: "#5B4BB5", cafe: "#8A5A12", bakery: "#C99A1B", takeout: "#2A8FBD", grocery: "#2F8F5B", salon_spa: "#B03A8C", clinic: "#D0521A", fitness: "#1F6FB2", retail: "#7A7A7A", daycare: "#E07B3C", office: "#9C9C9C", brewery: "#8B3A2E", other: "#9C9C9C" };

  function initMap(el, url, kind) {
    if (!window.L) return;
    const map = L.map(el, { scrollWheelZoom: false }).setView([43.70, -79.40], 11);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxZoom: 19,
    }).addTo(map);
    fetch(url + (url.includes("?") ? "&" : "?") + "_=" + Date.now()).then(r => r.json()).then(gj => {
      const layer = L.geoJSON(gj, {
        pointToLayer: (f, latlng) => {
          const p = f.properties;
          const color = kind === "teardown" ? (KIND_COLORS[p.kind] || "#555") : (CAT_COLORS[p.cat] || "#555");
          return L.circleMarker(latlng, { radius: kind === "teardown" ? 6 : 5 + Math.min(p.signals || 1, 4), color: "#fff", weight: 1, fillColor: color, fillOpacity: 0.9 });
        },
        onEachFeature: (f, l) => {
          const p = f.properties;
          const href = kind === "teardown" ? "/p/" + encodeURIComponent(p.id) : "/o/" + encodeURIComponent(p.id);
          const title = kind === "teardown" ? p.address : (p.name || "");
          const sub = kind === "teardown" ? p.headline + " · " + p.stage + " · filed " + p.filed : p.address + " · " + p.signals + " signal" + (p.signals > 1 ? "s" : "") + " · " + p.last;
          l.bindPopup("<b>" + esc(title) + "</b><br>" + esc(sub) + "<br><span style='color:#777'>" + esc(p.hood || "") + "</span><br><a href='" + href + "'>Open record →</a>");
        },
      }).addTo(map);
      if (gj.features.length) map.fitBounds(layer.getBounds().pad(0.05), { maxZoom: 15 });
      const n = document.getElementById("map-count");
      if (n) n.textContent = gj.features.length + " on map";
    });
    return map;
  }

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

  // Filter rail: checkboxes -> comma lists in the query string
  function wireFilters(form) {
    form.addEventListener("submit", e => {
      e.preventDefault();
      const q = new URLSearchParams();
      form.querySelectorAll("[data-group]").forEach(g => {
        const vals = Array.from(g.querySelectorAll("input:checked")).map(i => i.value);
        if (vals.length) q.set(g.dataset.group, vals.join(","));
      });
      form.querySelectorAll("select,input[type=text],input[type=number]").forEach(i => { if (i.value) q.set(i.name, i.value); });
      location.search = q.toString();
    });
    const reset = form.querySelector("[data-reset]");
    if (reset) reset.addEventListener("click", () => { location.search = ""; });
    const hoodSearch = form.querySelector("#hood-search");
    if (hoodSearch) hoodSearch.addEventListener("input", () => {
      const v = hoodSearch.value.toLowerCase();
      form.querySelectorAll(".hoods label").forEach(l => { l.hidden = v && !l.textContent.toLowerCase().includes(v); });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const m = document.getElementById("map");
    if (m) {
      const map = initMap(m, m.dataset.url + location.search.replace(/^\?/, m.dataset.url.includes("?") ? "&" : "?"), m.dataset.kind);
      const t = document.getElementById("map-toggle");
      if (t) t.addEventListener("click", () => { m.classList.toggle("hide"); if (!m.classList.contains("hide") && map) map.invalidateSize(); });
    }
    const mm = document.getElementById("minimap");
    if (mm && window.L) {
      const lat = +mm.dataset.lat, lon = +mm.dataset.lon;
      const map = L.map(mm, { scrollWheelZoom: false, zoomControl: false }).setView([lat, lon], 16);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: '&copy; OpenStreetMap contributors' }).addTo(map);
      L.circleMarker([lat, lon], { radius: 9, color: "#fff", weight: 2, fillColor: mm.dataset.color || "#D0521A", fillOpacity: 1 }).addTo(map);
    }
    const f = document.getElementById("filters");
    if (f) wireFilters(f);
  });
})();
