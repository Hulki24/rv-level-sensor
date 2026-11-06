const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(){this.nodes=new Map();this.style={};this.dataset={};this.classList={toggle(){}};this.children=[];this.textContent="";}
 querySelector(s){if(!this.nodes.has(s))this.nodes.set(s,new Element());return this.nodes.get(s);}
 appendChild(n){this.children.push(n);}
}
const elements=new Map();
const context={URL,HTMLElement:Element,document:{createElement(){return new Element()}},
 customElements:{get:k=>elements.get(k),define:(k,v)=>elements.set(k,v)},window:{},
 setInterval(){return 1},clearInterval(){},console};
vm.runInNewContext(fs.readFileSync('custom_components/xparkle_rvlevel/frontend/rv-level-card.js','utf8'),context);
const state=(value,attributes={})=>({state:String(value),attributes});
const h={states:{
 'sensor.rv_querneigung':state(-3.7),'sensor.rv_langsneigung':state(-.23),
 'sensor.rv_keil_vorne_links':state(0),'sensor.rv_keil_vorne_rechts':state(18),
 'sensor.rv_keil_hinten_links':state(0),'sensor.rv_keil_hinten_rechts':state(12),
 'sensor.rv_vorne_links_anheben':state(1.5),'sensor.rv_vorne_rechts_anheben':state(14.7),
 'sensor.rv_hinten_links_anheben':state(0),'sensor.rv_hinten_rechts_anheben':state(13.2),
 'sensor.rv_keilprofil':state('Eigener Keil'),
 'sensor.rv_keilempfehlung':state('Plan',{wedge_limit:2,stages:{front_right:2,rear_right:1},residual_longitudinal_angle:.077,residual_transverse_angle:.229})
}};
for(const name of ['xparkle-rv-level-top-card','xparkle-rv-level-side-card']){
 const card=new (elements.get(name))();card.setConfig({entity_prefix:'sensor.rv'});card.hass=h;
 assert.equal(card.heightText(card.wheelHeights().fl),'1,5 cm');
 assert.equal(card.heightText(card.wheelHeights().fr),'14,7 cm');
 assert.equal(card.heightText(card.wheelHeights().rl),'0,0 cm');
 assert.equal(card.heightText(card.wheelHeights().rr),'13,2 cm');
 assert.doesNotMatch(card.header('RV Level'),/xparkle-logo|<img/);
 if(name==='xparkle-rv-level-top-card'){
  assert.equal(card.querySelector('#fl').textContent,'1,5 cm');
  assert.equal(card.querySelector('#rr').textContent,'13,2 cm');
 }
 assert.deepEqual(Array.from(card.plan(card.vals()),v=>v.k),['fr','rr']);
 assert.match(card.querySelector('#wtitle').textContent,/2 von 2/);
 const rows=card.querySelector('#plan').children;
 assert.equal(rows[0].children[1].textContent,'vorne rechts');
 assert.equal(rows[1].children[1].textContent,'hinten rechts');
 assert.match(rows[0].children[3].textContent,/Stufe 2.*18 cm/);
 assert.match(rows[1].children[3].textContent,/Stufe 1/);
 assert.equal(rows.length,2);
 assert.doesNotMatch(card.innerHTML,/Theoretisch anheben/);
 assert.equal(card.tiltHint(0,0),'Nahezu waagerecht');
 assert.equal(card.tiltHint(0,-3.7),'Links höher');
 card.hass={states:{}};
 assert.equal(card.heightText(card.wheelHeights().fl),'—');
 assert.match(card.querySelector('#plan').textContent,/nicht verfügbar/);
}
console.log('Top and side render, correct wheels/stages, residual, level hint and missing data: passed');
const customStates={...h.states,
 'sensor.rv_fahrzeugprofil':state('Mein Adria',{
  custom_vehicle:true,top_image:'/local/womo/adria-top.png',
  side_image:'https://example.org/adria-side.png',
  body_length_m:7.4,body_width_m:2.3,body_height_m:3.0
 })
};
for(const [name,view,expected] of [
 ['xparkle-rv-level-top-card','top','/local/womo/adria-top.png'],
 ['xparkle-rv-level-side-card','side','https://example.org/adria-side.png']
]){
 const card=new (elements.get(name))();card.setConfig({entity_prefix:'sensor.rv'});card.hass={states:customStates};
 assert.equal(card.vehicleModel().model,'Mein Adria');
 assert.equal(card.querySelector('#modelBadge').textContent,'Mein Adria');
 const img=card.querySelector('#vehicleImg');
 assert.equal(img.src,expected);
 img.onerror();
 const fallback='/rv-level-sensor/vehicles/master4-semi-'+view+'.png';
 assert.equal(img.src,fallback);
 // A sensor refresh must not retry a broken URL over and over.
 card.hass={states:customStates};assert.equal(img.src,fallback);
 const next={...customStates,'sensor.rv_fahrzeugprofil':state('Fahrzeug B',{custom_vehicle:true,top_image:'/local/b.png',side_image:'/local/b.png'})};
 card.hass={states:next};assert.equal(img.src,'/local/b.png');
 assert.equal(card.safeImage('javascript:alert(1)'),'');
 assert.equal(card.safeImage('//example.org/image.png'),'');
 assert.equal(card.safeImage('/local/a.png'),'/local/a.png');
}
console.log('Personal profile names, images, profile switching and broken-image fallback: passed');

const imageCard=new (elements.get('xparkle-rv-level-top-card'))();
imageCard.setConfig({entity_prefix:'sensor.rv'});
imageCard.hass={states:customStates,hassUrl:path=>'https://ha.example'+path};
assert.equal(imageCard.querySelector('#vehicleImg').src,'https://ha.example/local/womo/adria-top.png');
assert.match(imageCard.innerHTML, /id="modelBadge"><\/div><div class="scene">/);
