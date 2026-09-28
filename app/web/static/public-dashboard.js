// First Dig zero-cold-start public dashboard.
// All records in these snapshots are already delay/redaction filtered at build time.
(function () {
  const BACKEND = "https://first-dig-night-shift.onrender.com";
  const COLORS = {
    teardown:{teardown:"#D0521A",new_house:"#E07B3C",multiplex:"#B03A8C",garden_suite:"#2F8F5B",major_addition:"#C99A1B",pool:"#2A8FBD",underpinning:"#7A7A7A",second_suite:"#9C9C9C",new_building:"#5B4BB5"},
    openings:{restaurant:"#137F68",bar:"#5B4BB5",cafe:"#8A5A12",bakery:"#C99A1B",takeout:"#2A8FBD",grocery:"#2F8F5B",salon_spa:"#B03A8C",clinic:"#D0521A",fitness:"#1F6FB2",retail:"#7A7A7A",daycare:"#E07B3C",office:"#9C9C9C",brewery:"#8B3A2E",other:"#9C9C9C"}
  };
  let map, layer;

  function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
  function qs(){return new URLSearchParams(location.search);}
  function list(p,k){return (p.get(k)||"").split(",").filter(Boolean);}
  function cutoff(days){const d=new Date();d.setDate(d.getDate()-days);return d.toISOString().slice(0,10);}
  function money(v){if(v==null||v==="")return "—";const n=Number(v);if(!Number.isFinite(n))return "—";return "$"+Math.round(n).toLocaleString("en-CA");}
  function product(){return document.documentElement.dataset.product==="openings"?"openings":"teardown";}

  function normalizedState(kind){
    const p=qs();
    if(kind==="teardown") return {
      days:Math.max(1,Math.min(3650,parseInt(p.get("days")||"30",10)||30)),
      kinds:list(p,"kinds"),stages:list(p,"stages"),hoods:list(p,"hoods"),
      mincost:Math.max(0,Number(p.get("mincost")||0)||0),q:(p.get("q")||"").trim().toLowerCase()
    };
    return {
      days:Math.max(1,Math.min(3650,parseInt(p.get("days")||"45",10)||45)),
      minsig:Math.max(1,Math.min(20,parseInt(p.get("minsig")||"1",10)||1)),
      city:p.get("city")||"toronto",cats:list(p,"cats"),hoods:list(p,"hoods"),
      q:(p.get("q")||"").trim().toLowerCase()
    };
  }

  function filterRecords(kind, records, s){
    const since=cutoff(s.days);
    if(kind==="teardown"){
      return records.filter(r =>
        (r.last_activity||"")>=since &&
        (!s.kinds.length||s.kinds.includes(r.kind)) &&
        (!s.stages.length||s.stages.includes(r.stage)) &&
        (!s.hoods.length||s.hoods.includes(r.neighbourhood)) &&
        (!s.mincost||Number(r.est_cost||0)>=s.mincost) &&
        (!s.q||[r.address,r.builder_name,r.description].some(v=>String(v||"").toLowerCase().includes(s.q)))
      );
    }
    const toronto = new Set(["TORONTO","NORTH YORK","SCARBOROUGH","ETOBICOKE","EAST YORK","YORK",""]);
    return records.filter(r =>
      (r.last_signal||"")>=since &&
      Number(r.signal_count||0)>=s.minsig &&
      (s.city!=="toronto"||toronto.has(String(r.city||"").toUpperCase())) &&
      (!s.cats.length||s.cats.includes(r.category)) &&
      (!s.hoods.length||s.hoods.includes(r.neighbourhood)) &&
      (!s.q||[r.name,r.address,r.owner].some(v=>String(v||"").toLowerCase().includes(s.q)))
    );
  }

  function renderTable(kind, records){
    const body=document.querySelector(".tbl tbody");
    if(!body)return;
    const rows=records.slice(0,500);
    if(!rows.length){
      body.innerHTML='<tr><td colspan="7" class="muted">Nothing matches. Widen the time window or clear a filter.</td></tr>';
      return;
    }
    if(kind==="teardown"){
      body.innerHTML=rows.map(r=>'<tr>'+
        '<td class="num">'+esc(r.first_filed||"")+'</td>'+
        '<td><a class="addr" href="'+BACKEND+'/p/'+encodeURIComponent(r.project_id)+'">'+esc(r.address||"")+'</a><span class="sub">'+esc(r.neighbourhood||"")+(r.postal?' · '+esc(r.postal):'')+'</span></td>'+
        '<td><span class="pill td">'+esc(r.kind_label||r.kind||"")+'</span><span class="sub">'+esc((r.description||"").slice(0,110))+'</span></td>'+
        '<td><span class="stage-cell"><span class="stage-glyph '+(r.stage==="completed"?"done":"current")+'"></span><span class="lbl">'+esc(r.stage_label||r.stage||"")+'</span></span></td>'+
        '<td class="r num">'+money(r.est_cost)+'</td>'+
        '<td>'+(r.builder_name?'<span class="value-tag">'+esc(r.builder_name)+'</span>':'<span class="muted">—</span>')+'</td>'+
        '<td class="num">'+esc(r.last_activity||"")+'</td></tr>').join("");
    } else {
      body.innerHTML=rows.map(r=>'<tr>'+
        '<td class="num">'+esc(r.last_signal||"")+'<span class="sub">first '+esc(r.first_signal||"")+'</span></td>'+
        '<td><a class="addr" href="'+BACKEND+'/o/'+encodeURIComponent(r.opening_id)+'">'+(r.name?'<span class="value-tag">'+esc(r.name)+'</span>':esc(r.category_label||""))+'</a></td>'+
        '<td><span class="pill op">'+esc(r.category_label||r.category||"")+'</span></td>'+
        '<td>'+esc(r.address||"")+'<span class="sub">'+esc(r.neighbourhood||r.city||"")+'</span></td>'+
        '<td><b class="num">'+esc(r.signal_count||0)+'</b> <span class="muted small">'+esc((r.signal_types||[]).join(" + "))+'</span></td>'+
        '<td>'+(r.phone?'<span class="value-tag">'+esc(r.phone)+'</span>':'<span class="muted">—</span>')+'</td>'+
        '<td class="r num">'+esc(r.score||"")+'</td></tr>').join("");
    }
  }

  function renderMap(kind, records){
    const el=document.getElementById("map");
    if(!el||!window.L)return;
    if(!map){
      map=L.map(el,{scrollWheelZoom:false}).setView([43.70,-79.40],11);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',maxZoom:19}).addTo(map);
    }
    if(layer) layer.remove();
    const features=records.filter(r=>Number.isFinite(Number(r.lat))&&Number.isFinite(Number(r.lon))).map(r=>({
      type:"Feature",
      geometry:{type:"Point",coordinates:[Number(r.lon),Number(r.lat)]},
      properties:r
    }));
    layer=L.geoJSON({type:"FeatureCollection",features},{
      pointToLayer:(f,ll)=>{
        const r=f.properties;
        const key=kind==="teardown"?r.kind:r.category;
        const c=(COLORS[kind]||{})[key]||"#555";
        return L.circleMarker(ll,{radius:kind==="teardown"?6:5+Math.min(Number(r.signal_count||1),4),color:"#fff",weight:1,fillColor:c,fillOpacity:.9});
      },
      onEachFeature:(f,l)=>{
        const r=f.properties;
        const href=kind==="teardown"?BACKEND+"/p/"+encodeURIComponent(r.project_id):BACKEND+"/o/"+encodeURIComponent(r.opening_id);
        const title=kind==="teardown"?(r.address||""):(r.name||r.category_label||"");
        const sub=kind==="teardown"?((r.headline||r.kind_label||"")+" · "+(r.stage_label||r.stage||"")+" · filed "+(r.first_filed||"")):((r.address||"")+" · "+(r.signal_count||0)+" signals · "+(r.last_signal||""));
        l.bindPopup("<b>"+esc(title)+"</b><br>"+esc(sub)+"<br><span style='color:#777'>"+esc(r.neighbourhood||"")+"</span><br><a href='"+href+"'>Open record →</a>");
      }
    }).addTo(map);
    if(features.length){
      const b=layer.getBounds();
      if(b.isValid())map.fitBounds(b.pad(.05),{maxZoom:15,animate:false});
    }else map.setView([43.70,-79.40],11);
    const n=document.getElementById("map-count");if(n)n.textContent=features.length+" on map";
    setTimeout(()=>map.invalidateSize(),50);
  }

  function syncControls(kind,s){
    const form=document.getElementById("filters");if(!form)return;
    const setVal=(name,v)=>{const el=form.querySelector('[name="'+name+'"]');if(el)el.value=String(v??"");};
    setVal("days",s.days); if(kind==="teardown") setVal("mincost",s.mincost||""); else {setVal("minsig",s.minsig);setVal("city",s.city);}
    setVal("q",s.q||"");
    form.querySelectorAll("[data-group]").forEach(g=>{
      const vals=s[g.dataset.group]||[];
      g.querySelectorAll("input[type=checkbox]").forEach(i=>i.checked=vals.includes(i.value));
    });
  }

  function buildQuery(form){
    const p=new URLSearchParams();
    form.querySelectorAll("[data-group]").forEach(g=>{
      const vals=Array.from(g.querySelectorAll("input:checked")).map(i=>i.value);
      if(vals.length)p.set(g.dataset.group,vals.join(","));
    });
    form.querySelectorAll("select,input[type=text],input[type=number]").forEach(i=>{
      if(i.name&&i.value)p.set(i.name,i.value);
    });
    return p;
  }

  async function boot(){
    const kind=product();
    const navToggle=document.getElementById("navToggle"),navLinks=document.getElementById("navLinks");
    if(navToggle&&navLinks)navToggle.addEventListener("click",()=>{const open=navLinks.classList.toggle("open");navToggle.setAttribute("aria-expanded",open?"true":"false");});

    const res=await fetch("/data/"+kind+".json",{cache:"no-store"});
    if(!res.ok)throw new Error("Snapshot unavailable");
    const payload=await res.json();
    const all=payload.records||[];

    const apply=()=>{
      const s=normalizedState(kind);syncControls(kind,s);
      const filtered=filterRecords(kind,all,s);
      const title=document.querySelector(".top h2");if(title)title.textContent=filtered.length+" "+(kind==="teardown"?(filtered.length===1?"project":"projects"):(filtered.length===1?"business":"businesses"));
      renderTable(kind,filtered);renderMap(kind,filtered);
    };

    const form=document.getElementById("filters");
    if(form){
      form.addEventListener("submit",e=>{e.preventDefault();const p=buildQuery(form);history.replaceState(null,"",location.pathname+(p.toString()?"?"+p:""));apply();});
      const reset=form.querySelector("[data-reset]");if(reset)reset.addEventListener("click",()=>{history.replaceState(null,"",location.pathname);apply();});
      const hs=form.querySelector("#hood-search");if(hs)hs.addEventListener("input",()=>{const v=hs.value.toLowerCase();form.querySelectorAll(".hoods label").forEach(l=>l.hidden=!!v&&!l.textContent.toLowerCase().includes(v));});
    }
    const toggle=document.getElementById("map-toggle");if(toggle)toggle.addEventListener("click",()=>{const el=document.getElementById("map");el.classList.toggle("hide");if(map&&!el.classList.contains("hide"))setTimeout(()=>map.invalidateSize(),50);});
    apply();
  }

  document.addEventListener("DOMContentLoaded",()=>boot().catch(err=>{
    console.error(err);
    const title=document.querySelector(".top h2");
    if(title)title.textContent="Data temporarily unavailable";
  }));
})();
