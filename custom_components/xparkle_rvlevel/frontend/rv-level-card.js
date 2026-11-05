const XP={
  ent(h,p,names){for(const n of names){const e=h?.states?.[`${p}_${n}`];if(e)return e}return null},
  num(h,p,names){const e=this.ent(h,p,names),v=e&&String(e.state).trim()!==""?Number(e.state):NaN;return Number.isFinite(v)?v:NaN},
  text(h,p,names){return this.ent(h,p,names)?.state??"—"},
  fmt(v,u="",d=1){return Number.isFinite(v)?v.toLocaleString("de-DE",{minimumFractionDigits:d,maximumFractionDigits:d})+u:"—"},
  stage(v,stages=[4,8,12]){if(!Number.isFinite(v)||v<=.5)return["Kein Keil","ok"];for(let i=0;i<stages.length;i++)if(v<=stages[i])return[`Stufe ${i+1} · ${String(stages[i]).replace('.',',')} cm`,"need"];return[`Stufe ${stages.length} reicht nicht`,"bad"]}
};
class XBase extends HTMLElement{
 setConfig(c){this.c={...c};this._resolvedPrefix=null}
 prefix(){
  if(this.c.entity_prefix)return this.c.entity_prefix.replace(/_+$/,'');
  const states=this.h?.states||{};
  const required=["querneigung","langsneigung","längsneigung","transverse_angle","longitudinal_angle"];
  const lift=["vorne_links_anheben","front_left_lift_cm","front_right_lift_cm","rear_left_lift_cm","rear_right_lift_cm"];
  const extra=["batterie","battery","keil_vorne_links","keil_vorne_rechts","keil_hinten_links","keil_hinten_rechts","fahrzeugprofil","vehicle_profile","keilprofil","wedge_profile"];
  const bases=new Set();
  for(const id of Object.keys(states)){
   if(!id.startsWith('sensor.'))continue;
   for(const sf of [...required,...lift,...extra])if(id.endsWith(`_${sf}`))bases.add(id.slice(0,-sf.length-1));
  }
  let best=null,bestScore=-1;
  for(const base of bases){
   let score=0,measure=0,lifts=0;
   for(const sf of required)if(states[`${base}_${sf}`]){score+=8;measure++}
   for(const sf of lift)if(states[`${base}_${sf}`]){score+=3;lifts++}
   for(const sf of extra)if(states[`${base}_${sf}`])score+=1;
   const p=base.replace(/^sensor\./,'');
   if(states[`button.${p}_connect`])score+=10;
   if(states[`button.${p}_disconnect`])score+=10;
   if(states[`binary_sensor.${p}_bluetooth_connection`]||states[`binary_sensor.${p}_connected`])score+=6;
   if(measure===0&&lifts===0)continue;
   if(score>bestScore){bestScore=score;best=base}
  }
  if(best){this._resolvedPrefix=best;return best}
  // Last-resort: derive a prefix from an RV Level connect button only when
  // corresponding sensor entities exist under the same base.
  for(const id of Object.keys(states))if(id.startsWith('button.')&&id.endsWith('_connect')){
   const p=id.slice(7,-8),base=`sensor.${p}`;
   if(Object.keys(states).some(x=>x.startsWith(base+'_'))){this._resolvedPrefix=base;return base}
  }
  return this._resolvedPrefix||'sensor.rvlevel_410f'
 }
 connectedCallback(){this._mounted=true}
 disconnectedCallback(){this._mounted=false;clearInterval(this._tick)}
 n(a){return XP.num(this.h,this.prefix(),a)} t(a){return XP.text(this.h,this.prefix(),a)}
 vals(){return {fl:this.n(["keil_vorne_links","wedge_front_left_cm"]),fr:this.n(["keil_vorne_rechts","wedge_front_right_cm"]),rl:this.n(["keil_hinten_links","wedge_rear_left_cm"]),rr:this.n(["keil_hinten_rechts","wedge_rear_right_cm"])}}
 wheelHeights(){
  return {fl:this.n(["vorne_links_anheben","front_left_lift_cm"]),fr:this.n(["vorne_rechts_anheben","front_right_lift_cm"]),rl:this.n(["hinten_links_anheben","rear_left_lift_cm"]),rr:this.n(["hinten_rechts_anheben","rear_right_lift_cm"])};
 }
 heightText(cm){return XP.fmt(cm," cm")}
 plan(v){return Object.entries(v).filter(([k,cm])=>Number.isFinite(cm)&&cm>0).map(([k,cm])=>({k,cm}))}
 planData(){return XP.ent(this.h,this.prefix(),["keilempfehlung","wedge_instruction"])?.attributes}
 planHtml(v){
  const names={fl:"vorne links",fr:"vorne rechts",rl:"hinten links",rr:"hinten rechts"},p=this.plan(v),meta=this.planData();
  const target=this.querySelector("#plan"),title=this.querySelector("#wtitle");
  if(!meta||meta.wedge_limit!==2||!Object.values(v).every(Number.isFinite)){
   title.textContent="Plan für maximal 2 Keile";target.textContent="Keilplan nicht verfügbar – Integration auf beta.6 aktualisieren und Sensor verbinden.";return;
  }
  title.textContent=p.length+" von 2 Keilen · "+this.wedgeName();
  target.innerHTML="";
  for(const [i,x] of p.entries()){
   const row=document.createElement("div");row.className="kr";
   for(const [column,text] of ["Keil "+(i+1),names[x.k],XP.fmt(x.cm," cm"),XP.stage(x.cm,this.wedgeStages())[0]].entries()){
    const el=document.createElement("span");if(column===3)el.className="st need";el.textContent=text;row.appendChild(el);
   }
   target.appendChild(row);
  }
  if(!p.length)target.textContent=meta.currently_level?"Keine Auffahrkeile erforderlich.":"Kein Keil verbessert die aktuelle Lage mit den verfügbaren Stufen.";
  const rest=document.createElement("div");rest.className="rest";rest.textContent="Restneigung geschätzt: längs "+XP.fmt(meta.residual_longitudinal_angle,"°",2)+" · quer "+XP.fmt(meta.residual_transverse_angle,"°",2)+". Federung und Untergrund können abweichen; live nachprüfen.";target.appendChild(rest);
 }
 tiltHint(l,q){if(!Number.isFinite(l)||!Number.isFinite(q))return "Keine Neigungsdaten";const parts=[];if(Math.abs(l)>.05)parts.push(l>0?"Vorne höher":"Hinten höher");if(Math.abs(q)>.05)parts.push(q>0?"Rechts höher":"Links höher");return parts.join(" · ")||"Nahezu waagerecht"}
 connId(k){const p=this.prefix().replace(/^sensor\./,"");const exact=`button.${p}_${k}`;if(this.h?.states?.[exact])return exact;const candidates=Object.keys(this.h?.states||{}).filter(id=>id.startsWith('button.')&&id.endsWith(`_${k}`));return candidates.find(id=>id.slice(7,-k.length-1)===p)||candidates[0]||exact}
 connected(){const p=this.prefix().replace(/^sensor\./,"");for(const id of [`binary_sensor.${p}_bluetooth_connection`,`binary_sensor.${p}_connected`,`sensor.${p}_bluetooth_connection`]){const e=this.h?.states?.[id];if(e)return ["on","connected","verbunden","true"].includes(String(e.state).toLowerCase())}return null}
 async press(k){const id=this.connId(k);if(this.h?.states?.[id])await this.h.callService("button","press",{entity_id:id})}
 wedgeName(){const x=this.t(['keilprofil','wedge_profile']);return x&&x!=='—'?x:'Milenco · Triple Level / Triple 3'}
 vehicleLabel(){const x=this.t(['fahrzeugprofil','vehicle_profile']);return x&&x!=='—'?x:'Ahorn Camp · Canada AD · 2019'}
 vehicleMeta(){return XP.ent(this.h,this.prefix(),["fahrzeugprofil","vehicle_profile"])?.attributes||{}}
 safeImage(value){if(typeof value!=="string"||!value.trim())return "";value=value.trim();if(value.startsWith("/")&&!value.startsWith("//"))return value;try{const url=new URL(value);return ["http:","https:"].includes(url.protocol)?url.href:""}catch{return ""}}
 setVehicleImage(img,view){
  const asset = this.vehicleAsset(view);
  const requested = asset.startsWith("/") ? this.h?.hassUrl?.(asset) ?? asset : asset;
  if(img.dataset.requested===requested)return;
  img.dataset.requested=requested;
  img.onerror=()=>{img.onerror=null;const fallback="/rv-level-sensor/vehicles/master4-semi-"+view+".png";img.src=this.h?.hassUrl?.(fallback)??fallback};
  img.src=requested;
 }
 vehicleModel(){const x=this.vehicleLabel();if(this.vehicleMeta().custom_vehicle)return {model:x,year:''};const m=x.match(/Ahorn Camp\s*·\s*(.*?)\s*·\s*(20\d{2})/);return m?{model:m[1],year:m[2]}:{model:'Canada AD',year:'2019'}}
  vehicleFamily(){return'master4-semi'}
 isCanadaAD(){return this.vehicleModel().model.trim().toLowerCase()==='canada ad'}
 isCanadaAD2019(){const {model,year}=this.vehicleModel();return model.trim().toLowerCase()==='canada ad'&&String(year)==='2019'}
 vehicleAsset(view){
  if(this.vehicleMeta().custom_vehicle)return this.safeImage(this.vehicleMeta()[view+'_image'])||'/rv-level-sensor/vehicles/master4-semi-'+view+'.png';
  if(this.isCanadaAD()){
   if(view==='top')return '/rv-level-sensor/ahorn-canada-ad-2019-top-clean.png';
   return this.isCanadaAD2019()
    ?'/rv-level-sensor/ahorn-canada-ad-2019-side-white-bumper.png'
    :'/rv-level-sensor/vehicles/canada-ad-side.png'
  }
  return `/rv-level-sensor/vehicles/master4-semi-${view}.png`
 }
 wedgeStages(){const n=this.wedgeName();const m=[[/Trident/i,[4,11,17]],[/Quattro/i,[4,8,12,18]],[/Thule/i,[4.4,7.8,11.2]],[/Froli.*XL/i,[6.5,11.5]],[/Froli/i,[4.5,7.5,10.5]],[/Premium S/i,[4,8,13]],[/Fiamma.*Level Up/i,[4,7,13]]];for(const [r,v] of m)if(r.test(n))return v;return[4,8,12]}
 header(title){return `<div class="head"><b>${title}<em class=ver>1.0.1-beta.14</em></b><span>🔋 <i id="bat">—</i>%</span></div><div class="conn"><span class="pill"><i></i><b class="ct">Verbindung</b></span><button class="cb">Connect</button></div>`}
 bind(){const b=this.querySelector('.cb');if(b)b.onclick=()=>this.press(this.connected()===true?'disconnect':'connect')}
 connRender(){const on=this.connected()===true,ct=this.querySelector('.ct'),b=this.querySelector('.cb'),dot=this.querySelector('.pill i');if(!ct)return;if(on&&!this._end)this._end=Date.now()+300000;if(!on)this._end=null;const timer=()=>{if(!this._end)return '';const sec=Math.max(0,Math.ceil((this._end-Date.now())/1000));const min=Math.floor(sec/60);return ` · Auto-Aus ${String(min).padStart(2,'0')}:${String(sec%60).padStart(2,'0')}`};ct.textContent=on?'Verbunden'+timer():'Getrennt';dot.classList.toggle('on',on);b.textContent=on?'Disconnect':'Connect';b.classList.toggle('off',on);clearInterval(this._tick);if(on)this._tick=setInterval(()=>{if(this._mounted&&this.querySelector('.ct'))this.querySelector('.ct').textContent='Verbunden'+timer()},1000)}
 level(label,val,max=3){const x=Number.isFinite(val)?Math.max(-1,Math.min(1,val/max)):0;return `<div class="lv"><small>${label} (${XP.fmt(val,'°',2)})</small><div class="tube"><span class="bubble" style="left:calc(50% + ${x*34}% - 14px)"></span><i></i></div></div>`}
 commonCss(){return `.wrap{padding:6px 9px 7px;background:radial-gradient(circle at 50% 25%,#0d1820 0,#081017 58%,#050a0e 100%);color:#f4f6f8}.head{display:grid;grid-template-columns:1fr auto;align-items:center;gap:7px;font-size:18px;min-height:31px}.head i{font-style:normal}.ver{font-style:normal;font-size:9px;margin-left:6px;padding:2px 5px;border-radius:7px;background:#0aa7e8;color:#fff;vertical-align:middle}.conn{display:flex;gap:8px;align-items:center;margin:3px 0 4px}.pill{background:#20262b;border-radius:11px;padding:5px 8px;display:flex;gap:7px;align-items:center;font-size:12px}.pill i{width:13px;height:13px;border-radius:50%;background:#777}.pill i.on{background:#34c83a;box-shadow:0 0 10px #34c83a55}.cb{border:0;border-radius:11px;padding:5px 9px;background:#168dd1;color:#fff;font-weight:800;font-size:12px}.cb.off{background:#ff3e39}.levels{margin-top:4px;background:#171d21;border-radius:13px;padding:5px 8px;display:grid;grid-template-columns:1fr 1fr;gap:12px}.levels h3{grid-column:1/3;margin:0;font-size:14px}.lv small{display:block;text-align:center;margin-bottom:4px}.tube{height:22px;border:4px solid #41494e;border-radius:16px;background:linear-gradient(#d8ff28,#8dca00 50%,#caff24);position:relative;box-shadow:inset 0 0 8px #243000}.tube:before,.tube:after,.tube i{content:"";position:absolute;top:0;bottom:0;width:1px;background:#202600}.tube:before{left:32%}.tube:after{right:32%}.tube i{left:50%}.bubble{position:absolute;top:2px;width:26px;height:14px;border-radius:12px;background:#9be31caa;border:1px solid #6ea800;box-shadow:inset 0 0 5px #fff8;transition:.25s}.keile{margin-top:4px;background:#171d21;border-radius:13px;padding:5px 9px}.mini-wedge{display:inline-block;position:relative;width:54px;height:22px;vertical-align:middle;margin:0 3px}.mini-wedge i{position:absolute;bottom:0;background:#ff3e39;border-radius:2px 2px 0 0}.mini-wedge i:nth-child(1){left:0;width:18px;height:7px}.mini-wedge i:nth-child(2){left:18px;width:18px;height:14px}.mini-wedge i:nth-child(3){left:36px;width:18px;height:21px}.rv-model-name{text-align:center;font-size:11px;color:#bfc6ca;padding:3px 0;overflow-wrap:anywhere}.height-note{text-align:center;font-size:11px;color:#c2c5c7;margin:5px 0 7px;line-height:1.4}.rest{font-size:12px;line-height:1.4;margin-top:8px;color:#c2c5c7}.kt{font-weight:900;margin-bottom:5px}.kr{display:grid;grid-template-columns:48px minmax(125px,1fr) 58px minmax(120px,auto);gap:8px;padding:4px 0;border-top:1px solid #30383d;align-items:center}.kr:first-of-type{border-top:0}.kr .st{white-space:nowrap}.bad{color:#ff413a}.need{color:#ffc52b}.ok{color:#3ddc66}@media(max-width:430px){.wrap{padding:6px 9px}.head{font-size:17px;gap:7px}.conn{gap:8px}.pill{padding:8px 10px}.cb{padding:7px 10px}.levels{gap:8px}.kr{grid-template-columns:46px 1fr 54px}.kr .st{grid-column:2/4;margin-top:1px}.mini-wedge{width:50px}.mini-wedge i:nth-child(1){width:16px}.mini-wedge i:nth-child(2){left:16px;width:17px}.mini-wedge i:nth-child(3){left:33px;width:17px}}`}
}
class XTop extends XBase{
 set hass(h){this.h=h;if(!this._built)this.build();this.render()}
 build(){this._built=1;this.innerHTML=`<ha-card><div class="wrap">${this.header('RV Level')}<div class="angles">Quer <b id="q">—</b> · Längs <b id="l">—</b></div><div class="front">VORDERSEITE</div><div class="rv-model-name" id="modelBadge"></div><div class="scene"><div class="m fl"><b id="fl">—</b><small>vorne links</small></div><div class="m fr"><b id="fr">—</b><small>vorne rechts</small></div><img class="topimg" id="vehicleImg" src="/rv-level-sensor/vehicles/master4-semi-top.png"><div class="m rl"><b id="rl">—</b><small>hinten links</small></div><div class="m rr"><b id="rr">—</b><small>hinten rechts</small></div></div><div class="rear">HINTEN</div><div class="height-note">Theoretisch anheben · aus Neigung berechnet<br>Keilplan für maximal 2 Keile separat unten</div><div class="levels"><h3>Wasserwaage</h3><div id="lvq"></div><div id="lvl"></div></div><div class="keile"><div class="kt" id="wtitle">2 Milenco Triple 3</div><div id="plan"></div></div></div></ha-card>`;const s=document.createElement('style');s.textContent=this.commonCss()+`.angles{margin:7px 2px 1px;font-size:13px}.front,.rear{text-align:center;color:#c9cdd0;font-size:13px}.scene{height:176px;position:relative}.topimg{position:absolute;left:50%;top:6%;height:74%;width:auto;transform:translateX(-50%) rotate(0deg)!important;object-fit:contain;filter:drop-shadow(0 8px 12px #0009)}.scene.rv-custom-top{height:224px}.rv-custom-top .topimg{top:0;height:100%;width:46%}.m{position:absolute;width:30%;font-size:13px}.m b{display:block;font-size:20px}.m small{color:#c2c5c7}.fl{left:3%;top:10%}.fr{right:3%;top:10%;text-align:right}.rl{left:3%;bottom:9%}.rr{right:3%;bottom:9%;text-align:right}@media(max-width:430px){.scene{height:170px}.topimg{height:73%}.m b{font-size:18px}}`;this.appendChild(s);this.bind()}
 render(){const q=this.n(["querneigung","transverse_angle"]),l=this.n(["langsneigung","längsneigung","longitudinal_angle"]),v=this.vals();this.querySelector('#bat').textContent=this.t(["batterie","battery"]);this.connRender();const vi=this.vehicleModel(),vim=this.querySelector('#vehicleImg');if(vim){this.querySelector('.scene').classList.toggle('rv-custom-top',!!this.vehicleMeta().custom_vehicle);this.setVehicleImage(vim,'top');}const mb=this.querySelector('#modelBadge');if(mb){const legacy=this.isCanadaAD2019();mb.textContent=this.vehicleMeta().custom_vehicle?vi.model:legacy?'':`${vi.model} · ${vi.year}`;mb.style.display=legacy?'none':'';}this.querySelector('#q').textContent=XP.fmt(q,'°',2);this.querySelector('#l').textContent=XP.fmt(l,'°',2);const heights=this.wheelHeights();for(const k of ['fl','fr','rl','rr'])this.querySelector('#'+k).textContent=this.heightText(heights[k]);this.querySelector('#lvq').innerHTML=this.level('Quer',q,3);this.querySelector('#lvl').innerHTML=this.level('Längs',l,3);this.planHtml(v)}

}
class XSide extends XBase{
 set hass(h){this.h=h;if(!this._built)this.build();this.render()}
 build(){this._built=1;this.innerHTML=`<ha-card><div class="wrap">${this.header('RV Level')}<div class="angle"><small>Längsneigung</small><b id="l">—</b></div><div class="hint" id="hint">—</div><div class="rv-model-name" id="modelBadge"></div><div class="stage"><img class="sideimg" id="vehicleImg" src="/rv-level-sensor/vehicles/master4-semi-side.png"><div class="ground"></div><span class="back">HINTEN</span><span class="fore">VORNE</span></div><div class="levels"><h3>Wasserwaage</h3><div id="lvq"></div><div id="lvl"></div></div><div class="keile"><div class="kt" id="wtitle">2 Milenco Triple 3</div><div id="plan"></div></div></div></ha-card>`;const s=document.createElement('style');s.textContent=this.commonCss()+`.angle{background:#171d21;border-radius:14px;padding:5px 9px;display:flex;align-items:center;gap:12px}.angle small{color:#c9cdd0}.angle b{font-size:25px}.hint{text-align:center;font-size:16px;font-weight:900;margin:3px 0 0}.stage{height:142px;position:relative;overflow:hidden}.sideimg{position:absolute;left:8%;width:84%;height:102px;top:18px;object-fit:contain;object-position:center;transform-origin:50% 88%;filter:drop-shadow(0 7px 9px #000b);transition:.25s}.ground{position:absolute;left:4%;right:4%;bottom:20px;height:3px;background:#50575c}.back,.fore{position:absolute;bottom:0}.back{left:5%}.fore{right:5%}.mini-wedge{display:inline-block;position:relative;width:54px;height:22px;vertical-align:middle;margin:0 3px}.mini-wedge i{position:absolute;bottom:0;background:#ff3e39;border-radius:2px 2px 0 0}.mini-wedge i:nth-child(1){left:0;width:18px;height:7px}.mini-wedge i:nth-child(2){left:18px;width:18px;height:14px}.mini-wedge i:nth-child(3){left:36px;width:18px;height:21px}.kr{grid-template-columns:48px minmax(125px,1fr) 58px minmax(120px,auto)}.kr .st{white-space:nowrap}@media(max-width:430px){.stage{height:136px}.sideimg{left:9%;width:82%;height:98px;top:17px}.kr{grid-template-columns:46px 1fr 54px}.kr .st{grid-column:2/4;margin-top:1px}.mini-wedge{width:50px}.mini-wedge i:nth-child(1){width:16px}.mini-wedge i:nth-child(2){left:16px;width:17px}.mini-wedge i:nth-child(3){left:33px;width:17px}}`;this.appendChild(s);this.bind()}
 render(){const l=this.n(["langsneigung","längsneigung","longitudinal_angle"]),q=this.n(["querneigung","transverse_angle"]),v=this.vals();this.querySelector('#bat').textContent=this.t(["batterie","battery"]);this.connRender();const vi=this.vehicleModel(),vim=this.querySelector('#vehicleImg');if(vim)this.setVehicleImage(vim,'side');const mb=this.querySelector('#modelBadge');if(mb){const legacy=this.isCanadaAD2019();mb.textContent=this.vehicleMeta().custom_vehicle?vi.model:legacy?'':`${vi.model} · ${vi.year}`;mb.style.display=legacy?'none':'';}this.querySelector('#l').textContent=XP.fmt(l,'°',2);this.querySelector('#hint').textContent=this.tiltHint(l,q);const img=this.querySelector('.sideimg');img.style.transform=`rotate(${Number.isFinite(l)?Math.max(-5,Math.min(5,-l*.8)):0}deg)`;this.querySelector('#lvq').innerHTML=this.level('Quer',q,3);this.querySelector('#lvl').innerHTML=this.level('Längs',l,3);this.planHtml(v)}
}
class XLegacy extends XTop{}
if(!customElements.get('xparkle-rv-level-top-card'))customElements.define('xparkle-rv-level-top-card',XTop);
if(!customElements.get('xparkle-rv-level-side-card'))customElements.define('xparkle-rv-level-side-card',XSide);
if(!customElements.get('xparkle-rv-level-card'))customElements.define('xparkle-rv-level-card',XLegacy);
window.customCards=window.customCards||[];window.customCards.push({type:'xparkle-rv-level-card',name:'Xparkle RV Level'},{type:'xparkle-rv-level-top-card',name:'Xparkle RV Level · Draufsicht'},{type:'xparkle-rv-level-side-card',name:'Xparkle RV Level · Seitenansicht'});
