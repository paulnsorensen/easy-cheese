import{g as e,h as t,m as n,p as r}from"./src-B_EVwkEo.js";import{o as i}from"./invert-DoGswQap.js";import{t as a}from"./channel-CJj7EsdS.js";import{S as o,n as s}from"./merge-CyOkP47b.js";import{V as c}from"./_createAssigner-C9pruyqs.js";import{A as l,E as u,R as d,c as f,m as p,v as m,w as h,x as g,z as _}from"./dist-wrAojYtf.js";import{t as v}from"./graphlib-C_n7KWQU.js";import{t as y}from"./index-3862675e-vXsPQsXy.js";function b(r){return typeof r==`string`?new n([document.querySelectorAll(r)],[document.documentElement]):new n([e(r)],t)}function x(e,t){return!!e.children(t).length}function S(e){return w(e.v)+`:`+w(e.w)+`:`+w(e.name)}var C=/:/g;function w(e){return e?String(e).replace(C,`\\:`):``}function T(e,t){t&&e.attr(`style`,t)}function E(e,t,n){t&&e.attr(`class`,t).attr(`class`,n+` `+e.attr(`class`))}function D(e,t){var n=t.graph();if(s(n)){var r=n.transition;if(c(r))return r(e)}return e}function O(e,t){var n=e.append(`foreignObject`).attr(`width`,`100000`),r=n.append(`xhtml:div`);r.attr(`xmlns`,`http://www.w3.org/1999/xhtml`);var i=t.label;switch(typeof i){case`function`:r.insert(i);break;case`object`:r.insert(function(){return i});break;default:r.html(i)}T(r,t.labelStyle),r.style(`display`,`inline-block`),r.style(`white-space`,`nowrap`);var a=r.node().getBoundingClientRect();return n.attr(`width`,a.width).attr(`height`,a.height),n}var k={},A=function(e){let t=Object.keys(e);for(let n of t)k[n]=e[n]},j=async function(e,t,n,r,i,a){let o=r.select(`[id="${n}"]`),s=Object.keys(e);for(let n of s){let r=e[n],s=`default`;r.classes.length>0&&(s=r.classes.join(` `)),s+=` flowchart-label`;let c=g(r.styles),d=r.text===void 0?r.id:r.text,h;if(u.info(`vertex`,r,r.labelType),r.labelType===`markdown`)u.info(`vertex`,r,r.labelType);else if(p(m().flowchart.htmlLabels))h=O(o,{label:d}).node(),h.parentNode.removeChild(h);else{let e=i.createElementNS(`http://www.w3.org/2000/svg`,`text`);e.setAttribute(`style`,c.labelStyle.replace(`color:`,`fill:`));let t=d.split(f.lineBreakRegex);for(let n of t){let t=i.createElementNS(`http://www.w3.org/2000/svg`,`tspan`);t.setAttributeNS(`http://www.w3.org/XML/1998/namespace`,`xml:space`,`preserve`),t.setAttribute(`dy`,`1em`),t.setAttribute(`x`,`1`),t.textContent=n,e.appendChild(t)}h=e}let _=0,v=``;switch(r.type){case`round`:_=5,v=`rect`;break;case`square`:v=`rect`;break;case`diamond`:v=`question`;break;case`hexagon`:v=`hexagon`;break;case`odd`:v=`rect_left_inv_arrow`;break;case`lean_right`:v=`lean_right`;break;case`lean_left`:v=`lean_left`;break;case`trapezoid`:v=`trapezoid`;break;case`inv_trapezoid`:v=`inv_trapezoid`;break;case`odd_right`:v=`rect_left_inv_arrow`;break;case`circle`:v=`circle`;break;case`ellipse`:v=`ellipse`;break;case`stadium`:v=`stadium`;break;case`subroutine`:v=`subroutine`;break;case`cylinder`:v=`cylinder`;break;case`group`:v=`rect`;break;case`doublecircle`:v=`doublecircle`;break;default:v=`rect`}let y=await l(d,m());t.setNode(r.id,{labelStyle:c.labelStyle,shape:v,labelText:y,labelType:r.labelType,rx:_,ry:_,class:s,style:c.style,id:r.id,link:r.link,linkTarget:r.linkTarget,tooltip:a.db.getTooltip(r.id)||``,domId:a.db.lookUpDomId(r.id),haveCallback:r.haveCallback,width:r.type===`group`?500:void 0,dir:r.dir,type:r.type,props:r.props,padding:m().flowchart.padding}),u.info(`setNode`,{labelStyle:c.labelStyle,labelType:r.labelType,shape:v,labelText:y,rx:_,ry:_,class:s,style:c.style,id:r.id,domId:a.db.lookUpDomId(r.id),width:r.type===`group`?500:void 0,type:r.type,dir:r.dir,props:r.props,padding:m().flowchart.padding})}},M=async function(e,t,n){u.info(`abc78 edges = `,e);let r=0,i={},a,s;if(e.defaultStyle!==void 0){let t=g(e.defaultStyle);a=t.style,s=t.labelStyle}for(let n of e){r++;let c=`L-`+n.start+`-`+n.end;i[c]===void 0?(i[c]=0,u.info(`abc78 new entry`,c,i[c])):(i[c]++,u.info(`abc78 new entry`,c,i[c]));let d=c+`-`+i[c];u.info(`abc78 new link id to be used is`,c,d,i[c]);let p=`LS-`+n.start,_=`LE-`+n.end,v={style:``,labelStyle:``};switch(v.minlen=n.length||1,v.arrowhead=n.type===`arrow_open`?`none`:`normal`,v.arrowTypeStart=`arrow_open`,v.arrowTypeEnd=`arrow_open`,n.type){case`double_arrow_cross`:v.arrowTypeStart=`arrow_cross`;case`arrow_cross`:v.arrowTypeEnd=`arrow_cross`;break;case`double_arrow_point`:v.arrowTypeStart=`arrow_point`;case`arrow_point`:v.arrowTypeEnd=`arrow_point`;break;case`double_arrow_circle`:v.arrowTypeStart=`arrow_circle`;case`arrow_circle`:v.arrowTypeEnd=`arrow_circle`}let y=``,b=``;switch(n.stroke){case`normal`:y=`fill:none;`,a!==void 0&&(y=a),s!==void 0&&(b=s),v.thickness=`normal`,v.pattern=`solid`;break;case`dotted`:v.thickness=`normal`,v.pattern=`dotted`,v.style=`fill:none;stroke-width:2px;stroke-dasharray:3;`;break;case`thick`:v.thickness=`thick`,v.pattern=`solid`,v.style=`stroke-width: 3.5px;fill:none;`;break;case`invisible`:v.thickness=`invisible`,v.pattern=`solid`,v.style=`stroke-width: 0;fill:none;`}if(n.style!==void 0){let e=g(n.style);y=e.style,b=e.labelStyle}v.style=v.style+=y,v.labelStyle=v.labelStyle+=b,v.curve=n.interpolate===void 0?e.defaultInterpolate===void 0?h(k.curve,o):h(e.defaultInterpolate,o):h(n.interpolate,o),n.text===void 0?n.style!==void 0&&(v.arrowheadStyle=`fill: #333`):(v.arrowheadStyle=`fill: #333`,v.labelpos=`c`),v.labelType=n.labelType,v.label=await l(n.text.replace(f.lineBreakRegex,`
`),m()),n.style===void 0&&(v.style=v.style||`stroke: #333; stroke-width: 1.5px;fill:none;`),v.labelStyle=v.labelStyle.replace(`color:`,`fill:`),v.id=d,v.classes=`flowchart-link `+p+` `+_,t.setEdge(n.start,n.end,v,r)}},N={setConf:A,addVertices:j,addEdges:M,getClasses:function(e,t){return t.db.getClasses()},draw:async function(e,t,n,i){u.info(`Drawing flowchart`);let a=i.db.getDirection();a===void 0&&(a=`TD`);let{securityLevel:o,flowchart:s}=m(),c=s.nodeSpacing||50,l=s.rankSpacing||50,f;o===`sandbox`&&(f=r(`#i`+t));let p=r(o===`sandbox`?f.nodes()[0].contentDocument.body:`body`),h=o===`sandbox`?f.nodes()[0].contentDocument:document,g=new v({multigraph:!0,compound:!0}).setGraph({rankdir:a,nodesep:c,ranksep:l,marginx:0,marginy:0}).setDefaultEdgeLabel(function(){return{}}),x,S=i.db.getSubGraphs();u.info(`Subgraphs - `,S);for(let e=S.length-1;e>=0;e--)x=S[e],u.info(`Subgraph - `,x),i.db.addVertex(x.id,{text:x.title,type:x.labelType},`group`,void 0,x.classes,x.dir);let C=i.db.getVertices(),w=i.db.getEdges();u.info(`Edges`,w);let T=0;for(T=S.length-1;T>=0;T--){x=S[T],b(`cluster`).append(`text`);for(let e=0;e<x.nodes.length;e++)u.info(`Setting up subgraphs`,x.nodes[e],x.id),g.setParent(x.nodes[e],x.id)}await j(C,g,t,p,h,i),await M(w,g);let E=p.select(`[id="${t}"]`),D=p.select(`#`+t+` g`);if(await y(D,g,[`point`,`circle`,`cross`],`flowchart`,t),_.insertTitle(E,`flowchartTitleText`,s.titleTopMargin,i.db.getDiagramTitle()),d(g,E,s.diagramPadding,s.useMaxWidth),i.db.indexNodes(`subGraph`+T),!s.htmlLabels){let e=h.querySelectorAll(`[id="`+t+`"] .edgeLabel .label`);for(let t of e){let e=t.getBBox(),n=h.createElementNS(`http://www.w3.org/2000/svg`,`rect`);n.setAttribute(`rx`,0),n.setAttribute(`ry`,0),n.setAttribute(`width`,e.width),n.setAttribute(`height`,e.height),t.insertBefore(n,t.firstChild)}}Object.keys(C).forEach(function(e){let n=C[e];if(n.link){let i=r(`#`+t+` [id="`+e+`"]`);if(i){let e=h.createElementNS(`http://www.w3.org/2000/svg`,`a`);e.setAttributeNS(`http://www.w3.org/2000/svg`,`class`,n.classes.join(` `)),e.setAttributeNS(`http://www.w3.org/2000/svg`,`href`,n.link),e.setAttributeNS(`http://www.w3.org/2000/svg`,`rel`,`noopener`),o===`sandbox`?e.setAttributeNS(`http://www.w3.org/2000/svg`,`target`,`_top`):n.linkTarget&&e.setAttributeNS(`http://www.w3.org/2000/svg`,`target`,n.linkTarget);let t=i.insert(function(){return e},`:first-child`),r=i.select(`.label-container`);r&&t.append(function(){return r.node()});let a=i.select(`.label`);a&&t.append(function(){return a.node()})}}})}},P=(e,t)=>{let n=a,r=n(e,`r`),o=n(e,`g`),s=n(e,`b`);return i(r,o,s,t)},F=e=>`.label {
    font-family: ${e.fontFamily};
    color: ${e.nodeTextColor||e.textColor};
  }
  .cluster-label text {
    fill: ${e.titleColor};
  }
  .cluster-label span,p {
    color: ${e.titleColor};
  }

  .label text,span,p {
    fill: ${e.nodeTextColor||e.textColor};
    color: ${e.nodeTextColor||e.textColor};
  }

  .node rect,
  .node circle,
  .node ellipse,
  .node polygon,
  .node path {
    fill: ${e.mainBkg};
    stroke: ${e.nodeBorder};
    stroke-width: 1px;
  }
  .flowchart-label text {
    text-anchor: middle;
  }
  // .flowchart-label .text-outer-tspan {
  //   text-anchor: middle;
  // }
  // .flowchart-label .text-inner-tspan {
  //   text-anchor: start;
  // }

  .node .katex path {
    fill: #000;
    stroke: #000;
    stroke-width: 1px;
  }

  .node .label {
    text-align: center;
  }
  .node.clickable {
    cursor: pointer;
  }

  .arrowheadPath {
    fill: ${e.arrowheadColor};
  }

  .edgePath .path {
    stroke: ${e.lineColor};
    stroke-width: 2.0px;
  }

  .flowchart-link {
    stroke: ${e.lineColor};
    fill: none;
  }

  .edgeLabel {
    background-color: ${e.edgeLabelBackground};
    rect {
      opacity: 0.5;
      background-color: ${e.edgeLabelBackground};
      fill: ${e.edgeLabelBackground};
    }
    text-align: center;
  }

  /* For html labels only */
  .labelBkg {
    background-color: ${P(e.edgeLabelBackground,.5)};
    // background-color: 
  }

  .cluster rect {
    fill: ${e.clusterBkg};
    stroke: ${e.clusterBorder};
    stroke-width: 1px;
  }

  .cluster text {
    fill: ${e.titleColor};
  }

  .cluster span,p {
    color: ${e.titleColor};
  }
  /* .cluster div {
    color: ${e.titleColor};
  } */

  div.mermaidTooltip {
    position: absolute;
    text-align: center;
    max-width: 200px;
    padding: 2px;
    font-family: ${e.fontFamily};
    font-size: 12px;
    background: ${e.tertiaryColor};
    border: 1px solid ${e.border2};
    border-radius: 2px;
    pointer-events: none;
    z-index: 100;
  }

  .flowchartTitleText {
    text-anchor: middle;
    font-size: 18px;
    fill: ${e.textColor};
  }
`;export{T as a,x as c,E as i,b as l,F as n,D as o,O as r,S as s,N as t};