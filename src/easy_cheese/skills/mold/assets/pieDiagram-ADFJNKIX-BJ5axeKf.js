import{g as U,s as q,a as V,b as Z,q as j,p as H,_ as s,l as w,c as J,D as K,I as Q,L as X,e as Y,y as ee,E as te}from"./index-uA5YUCmt.js";import{p as ae}from"./chunk-4BX2VUAB-BdkX2FCJ.js";import{p as re}from"./treemap-KMMF4GRG-CphJwMsq.js";import{a as G}from"./arc-Csi8s6Qx.js";import{o as ie}from"./ordinal-Cboi1Yqb.js";import{p as se}from"./pie-qNKrkCpS.js";import"./_baseUniq-BSLMA6Vs.js";import"./_basePickBy-avNnuA08.js";import"./has-ClkinfFy.js";import"./clone-DicgUksU.js";import"./init-Gi6I4Gst.js";var oe=te.pie,D={sections:new Map,showData:!1},g=D.sections,C=D.showData,le=structuredClone(oe),ne=s(()=>structuredClone(le),"getConfig"),ce=s(()=>{g=new Map,C=D.showData,ee()},"clear"),pe=s(({label:e,value:a})=>{if(a<0)throw new Error(`"${e}" has invalid value: ${a}. Negative values are not allowed in pie charts. All slice values must be >= 0.`);g.has(e)||(g.set(e,a),w.debug(`added new section: ${e}, with value: ${a}`))},"addSection"),de=s(()=>g,"getSections"),ge=s(e=>{C=e},"setShowData"),ue=s(()=>C,"getShowData"),W={getConfig:ne,clear:ce,setDiagramTitle:H,getDiagramTitle:j,setAccTitle:Z,getAccTitle:V,setAccDescription:q,getAccDescription:U,addSection:pe,getSections:de,setShowData:ge,getShowData:ue},fe=s((e,a)=>{ae(e,a),a.setShowData(e.showData),e.sections.map(a.addSection)},"populateDb"),me={parse:s(async e=>{const a=await re("pie",e);w.debug(a),fe(a,W)},"parse")},he=s(e=>`
  .pieCircle{
    stroke: ${e.pieStrokeColor};
    stroke-width : ${e.pieStrokeWidth};
    opacity : ${e.pieOpacity};
  }
  .pieOuterCircle{
    stroke: ${e.pieOuterStrokeColor};
    stroke-width: ${e.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${e.pieTitleTextSize};
    fill: ${e.pieTitleTextColor};
    font-family: ${e.fontFamily};
  }
  .slice {
    font-family: ${e.fontFamily};
    fill: ${e.pieSectionTextColor};
    font-size:${e.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${e.pieLegendTextColor};
    font-family: ${e.fontFamily};
    font-size: ${e.pieLegendTextSize};
  }
`,"getStyles"),ve=he,Se=s(e=>{const a=[...e.values()].reduce((r,o)=>r+o,0),$=[...e.entries()].map(([r,o])=>({label:r,value:o})).filter(r=>r.value/a*100>=1).sort((r,o)=>o.value-r.value);return se().value(r=>r.value)($)},"createPieArcs"),xe=s((e,a,$,y)=>{w.debug(`rendering pie chart
`+e);const r=y.db,o=J(),T=K(r.getConfig(),o.pie),A=40,l=18,p=4,c=450,u=c,f=Q(a),n=f.append("g");n.attr("transform","translate("+u/2+","+c/2+")");const{themeVariables:i}=o;let[b]=X(i.pieOuterStrokeWidth);b??=2;const E=T.textPosition,d=Math.min(u,c)/2-A,I=G().innerRadius(0).outerRadius(d),L=G().innerRadius(d*E).outerRadius(d*E);n.append("circle").attr("cx",0).attr("cy",0).attr("r",d+b/2).attr("class","pieOuterCircle");const m=r.getSections(),M=Se(m),O=[i.pie1,i.pie2,i.pie3,i.pie4,i.pie5,i.pie6,i.pie7,i.pie8,i.pie9,i.pie10,i.pie11,i.pie12];let h=0;m.forEach(t=>{h+=t});const _=M.filter(t=>(t.data.value/h*100).toFixed(0)!=="0"),v=ie(O);n.selectAll("mySlices").data(_).enter().append("path").attr("d",I).attr("fill",t=>v(t.data.label)).attr("class","pieCircle"),n.selectAll("mySlices").data(_).enter().append("text").text(t=>(t.data.value/h*100).toFixed(0)+"%").attr("transform",t=>"translate("+L.centroid(t)+")").style("text-anchor","middle").attr("class","slice"),n.append("text").text(r.getDiagramTitle()).attr("x",0).attr("y",-400/2).attr("class","pieTitleText");const k=[...m.entries()].map(([t,x])=>({label:t,value:x})),S=n.selectAll(".legend").data(k).enter().append("g").attr("class","legend").attr("transform",(t,x)=>{const F=l+p,R=F*k.length/2,N=12*l,B=x*F-R;return"translate("+N+","+B+")"});S.append("rect").attr("width",l).attr("height",l).style("fill",t=>v(t.label)).style("stroke",t=>v(t.label)),S.append("text").attr("x",l+p).attr("y",l-p).text(t=>r.getShowData()?`${t.label} [${t.value}]`:t.label);const P=Math.max(...S.selectAll("text").nodes().map(t=>t?.getBoundingClientRect().width??0)),z=u+A+l+p+P;f.attr("viewBox",`0 0 ${z} ${c}`),Y(f,c,z,T.useMaxWidth)},"draw"),we={draw:xe},Fe={parser:me,db:W,renderer:we,styles:ve};export{Fe as diagram};
