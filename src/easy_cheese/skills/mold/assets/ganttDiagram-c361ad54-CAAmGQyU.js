import{a as e}from"./rolldown-runtime-Dqfqb5bO.js";import{_ as t,p as n}from"./src-B_EVwkEo.js";import{t as r}from"./linear-Dz14sTxM.js";import{C as i,S as a,_ as o,a as s,b as c,c as l,d as u,f as d,g as f,h as p,i as m,l as h,m as g,n as _,o as v,p as y,r as b,s as x,t as S,u as C,v as w,x as T,y as E}from"./advancedFormat-Ci0lZjOs.js";import{U as D}from"./index-DN1RkdDE.js";import{E as O,I as k,N as A,P as j,V as ee,_ as te,b as ne,c as re,g as ie,s as ae,u as oe,v as M,z as se}from"./dist-wrAojYtf.js";var ce=D(),N=e(t(),1),le=e(b(),1),ue=e(_(),1),de=e(S(),1);ee();var fe=function(){var e=function(e,t,n,r){for(n||={},r=e.length;r--;n[e[r]]=t);return n},t=[6,8,10,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,30,32,33,35,37],n=[1,25],r=[1,26],i=[1,27],a=[1,28],o=[1,29],s=[1,30],c=[1,31],l=[1,9],u=[1,10],d=[1,11],f=[1,12],p=[1,13],m=[1,14],h=[1,15],g=[1,16],_=[1,18],v=[1,19],y=[1,20],b=[1,21],x=[1,22],S=[1,24],C=[1,32],w={trace:function(){},yy:{},symbols_:{error:2,start:3,gantt:4,document:5,EOF:6,line:7,SPACE:8,statement:9,NL:10,weekday:11,weekday_monday:12,weekday_tuesday:13,weekday_wednesday:14,weekday_thursday:15,weekday_friday:16,weekday_saturday:17,weekday_sunday:18,dateFormat:19,inclusiveEndDates:20,topAxis:21,axisFormat:22,tickInterval:23,excludes:24,includes:25,todayMarker:26,title:27,acc_title:28,acc_title_value:29,acc_descr:30,acc_descr_value:31,acc_descr_multiline_value:32,section:33,clickStatement:34,taskTxt:35,taskData:36,click:37,callbackname:38,callbackargs:39,href:40,clickStatementDebug:41,$accept:0,$end:1},terminals_:{2:`error`,4:`gantt`,6:`EOF`,8:`SPACE`,10:`NL`,12:`weekday_monday`,13:`weekday_tuesday`,14:`weekday_wednesday`,15:`weekday_thursday`,16:`weekday_friday`,17:`weekday_saturday`,18:`weekday_sunday`,19:`dateFormat`,20:`inclusiveEndDates`,21:`topAxis`,22:`axisFormat`,23:`tickInterval`,24:`excludes`,25:`includes`,26:`todayMarker`,27:`title`,28:`acc_title`,29:`acc_title_value`,30:`acc_descr`,31:`acc_descr_value`,32:`acc_descr_multiline_value`,33:`section`,35:`taskTxt`,36:`taskData`,37:`click`,38:`callbackname`,39:`callbackargs`,40:`href`},productions_:[0,[3,3],[5,0],[5,2],[7,2],[7,1],[7,1],[7,1],[11,1],[11,1],[11,1],[11,1],[11,1],[11,1],[11,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,2],[9,2],[9,1],[9,1],[9,1],[9,2],[34,2],[34,3],[34,3],[34,4],[34,3],[34,4],[34,2],[41,2],[41,3],[41,3],[41,4],[41,3],[41,4],[41,2]],performAction:function(e,t,n,r,i,a,o){var s=a.length-1;switch(i){case 1:return a[s-1];case 2:this.$=[];break;case 3:a[s-1].push(a[s]),this.$=a[s-1];break;case 4:case 5:this.$=a[s];break;case 6:case 7:this.$=[];break;case 8:r.setWeekday(`monday`);break;case 9:r.setWeekday(`tuesday`);break;case 10:r.setWeekday(`wednesday`);break;case 11:r.setWeekday(`thursday`);break;case 12:r.setWeekday(`friday`);break;case 13:r.setWeekday(`saturday`);break;case 14:r.setWeekday(`sunday`);break;case 15:r.setDateFormat(a[s].substr(11)),this.$=a[s].substr(11);break;case 16:r.enableInclusiveEndDates(),this.$=a[s].substr(18);break;case 17:r.TopAxis(),this.$=a[s].substr(8);break;case 18:r.setAxisFormat(a[s].substr(11)),this.$=a[s].substr(11);break;case 19:r.setTickInterval(a[s].substr(13)),this.$=a[s].substr(13);break;case 20:r.setExcludes(a[s].substr(9)),this.$=a[s].substr(9);break;case 21:r.setIncludes(a[s].substr(9)),this.$=a[s].substr(9);break;case 22:r.setTodayMarker(a[s].substr(12)),this.$=a[s].substr(12);break;case 24:r.setDiagramTitle(a[s].substr(6)),this.$=a[s].substr(6);break;case 25:this.$=a[s].trim(),r.setAccTitle(this.$);break;case 26:case 27:this.$=a[s].trim(),r.setAccDescription(this.$);break;case 28:r.addSection(a[s].substr(8)),this.$=a[s].substr(8);break;case 30:r.addTask(a[s-1],a[s]),this.$=`task`;break;case 31:this.$=a[s-1],r.setClickEvent(a[s-1],a[s],null);break;case 32:this.$=a[s-2],r.setClickEvent(a[s-2],a[s-1],a[s]);break;case 33:this.$=a[s-2],r.setClickEvent(a[s-2],a[s-1],null),r.setLink(a[s-2],a[s]);break;case 34:this.$=a[s-3],r.setClickEvent(a[s-3],a[s-2],a[s-1]),r.setLink(a[s-3],a[s]);break;case 35:this.$=a[s-2],r.setClickEvent(a[s-2],a[s],null),r.setLink(a[s-2],a[s-1]);break;case 36:this.$=a[s-3],r.setClickEvent(a[s-3],a[s-1],a[s]),r.setLink(a[s-3],a[s-2]);break;case 37:this.$=a[s-1],r.setLink(a[s-1],a[s]);break;case 38:case 44:this.$=a[s-1]+` `+a[s];break;case 39:case 40:case 42:this.$=a[s-2]+` `+a[s-1]+` `+a[s];break;case 41:case 43:this.$=a[s-3]+` `+a[s-2]+` `+a[s-1]+` `+a[s]}},table:[{3:1,4:[1,2]},{1:[3]},e(t,[2,2],{5:3}),{6:[1,4],7:5,8:[1,6],9:7,10:[1,8],11:17,12:n,13:r,14:i,15:a,16:o,17:s,18:c,19:l,20:u,21:d,22:f,23:p,24:m,25:h,26:g,27:_,28:v,30:y,32:b,33:x,34:23,35:S,37:C},e(t,[2,7],{1:[2,1]}),e(t,[2,3]),{9:33,11:17,12:n,13:r,14:i,15:a,16:o,17:s,18:c,19:l,20:u,21:d,22:f,23:p,24:m,25:h,26:g,27:_,28:v,30:y,32:b,33:x,34:23,35:S,37:C},e(t,[2,5]),e(t,[2,6]),e(t,[2,15]),e(t,[2,16]),e(t,[2,17]),e(t,[2,18]),e(t,[2,19]),e(t,[2,20]),e(t,[2,21]),e(t,[2,22]),e(t,[2,23]),e(t,[2,24]),{29:[1,34]},{31:[1,35]},e(t,[2,27]),e(t,[2,28]),e(t,[2,29]),{36:[1,36]},e(t,[2,8]),e(t,[2,9]),e(t,[2,10]),e(t,[2,11]),e(t,[2,12]),e(t,[2,13]),e(t,[2,14]),{38:[1,37],40:[1,38]},e(t,[2,4]),e(t,[2,25]),e(t,[2,26]),e(t,[2,30]),e(t,[2,31],{39:[1,39],40:[1,40]}),e(t,[2,37],{38:[1,41]}),e(t,[2,32],{40:[1,42]}),e(t,[2,33]),e(t,[2,35],{39:[1,43]}),e(t,[2,34]),e(t,[2,36])],defaultActions:{},parseError:function(e,t){if(t.recoverable)this.trace(e);else{var n=Error(e);throw n.hash=t,n}},parse:function(e){var t=this,n=[0],r=[],i=[null],a=[],o=this.table,s=``,c=0,l=0,u=2,d=1,f=a.slice.call(arguments,1),p=Object.create(this.lexer),m={yy:{}};for(var h in this.yy)Object.prototype.hasOwnProperty.call(this.yy,h)&&(m.yy[h]=this.yy[h]);p.setInput(e,m.yy),m.yy.lexer=p,m.yy.parser=this,p.yylloc===void 0&&(p.yylloc={});var g=p.yylloc;a.push(g);var _=p.options&&p.options.ranges;this.parseError=typeof m.yy.parseError==`function`?m.yy.parseError:Object.getPrototypeOf(this).parseError;function v(){var e=r.pop()||p.lex()||d;return typeof e!=`number`&&(e instanceof Array&&(r=e,e=r.pop()),e=t.symbols_[e]||e),e}for(var y,b,x,S,C={},w,T,E,D;;){if(b=n[n.length-1],this.defaultActions[b]?x=this.defaultActions[b]:(y??=v(),x=o[b]&&o[b][y]),x===void 0||!x.length||!x[0]){var O=``;for(w in D=[],o[b])this.terminals_[w]&&w>u&&D.push(`'`+this.terminals_[w]+`'`);O=p.showPosition?`Parse error on line `+(c+1)+`:
`+p.showPosition()+`
Expecting `+D.join(`, `)+`, got '`+(this.terminals_[y]||y)+`'`:`Parse error on line `+(c+1)+`: Unexpected `+(y==d?`end of input`:`'`+(this.terminals_[y]||y)+`'`),this.parseError(O,{text:p.match,token:this.terminals_[y]||y,line:p.yylineno,loc:g,expected:D})}if(x[0]instanceof Array&&x.length>1)throw Error(`Parse Error: multiple actions possible at state: `+b+`, token: `+y);switch(x[0]){case 1:n.push(y),i.push(p.yytext),a.push(p.yylloc),n.push(x[1]),y=null,l=p.yyleng,s=p.yytext,c=p.yylineno,g=p.yylloc;break;case 2:if(T=this.productions_[x[1]][1],C.$=i[i.length-T],C._$={first_line:a[a.length-(T||1)].first_line,last_line:a[a.length-1].last_line,first_column:a[a.length-(T||1)].first_column,last_column:a[a.length-1].last_column},_&&(C._$.range=[a[a.length-(T||1)].range[0],a[a.length-1].range[1]]),S=this.performAction.apply(C,[s,l,c,m.yy,x[1],i,a].concat(f)),S!==void 0)return S;T&&(n=n.slice(0,-1*T*2),i=i.slice(0,-1*T),a=a.slice(0,-1*T)),n.push(this.productions_[x[1]][0]),i.push(C.$),a.push(C._$),E=o[n[n.length-2]][n[n.length-1]],n.push(E);break;case 3:return!0}}return!0}};w.lexer=function(){return{EOF:1,parseError:function(e,t){if(this.yy.parser)this.yy.parser.parseError(e,t);else throw Error(e)},setInput:function(e,t){return this.yy=t||this.yy||{},this._input=e,this._more=this._backtrack=this.done=!1,this.yylineno=this.yyleng=0,this.yytext=this.matched=this.match=``,this.conditionStack=[`INITIAL`],this.yylloc={first_line:1,first_column:0,last_line:1,last_column:0},this.options.ranges&&(this.yylloc.range=[0,0]),this.offset=0,this},input:function(){var e=this._input[0];return this.yytext+=e,this.yyleng++,this.offset++,this.match+=e,this.matched+=e,e.match(/(?:\r\n?|\n).*/g)?(this.yylineno++,this.yylloc.last_line++):this.yylloc.last_column++,this.options.ranges&&this.yylloc.range[1]++,this._input=this._input.slice(1),e},unput:function(e){var t=e.length,n=e.split(/(?:\r\n?|\n)/g);this._input=e+this._input,this.yytext=this.yytext.substr(0,this.yytext.length-t),this.offset-=t;var r=this.match.split(/(?:\r\n?|\n)/g);this.match=this.match.substr(0,this.match.length-1),this.matched=this.matched.substr(0,this.matched.length-1),n.length-1&&(this.yylineno-=n.length-1);var i=this.yylloc.range;return this.yylloc={first_line:this.yylloc.first_line,last_line:this.yylineno+1,first_column:this.yylloc.first_column,last_column:n?(n.length===r.length?this.yylloc.first_column:0)+r[r.length-n.length].length-n[0].length:this.yylloc.first_column-t},this.options.ranges&&(this.yylloc.range=[i[0],i[0]+this.yyleng-t]),this.yyleng=this.yytext.length,this},more:function(){return this._more=!0,this},reject:function(){if(this.options.backtrack_lexer)this._backtrack=!0;else return this.parseError(`Lexical error on line `+(this.yylineno+1)+`. You can only invoke reject() in the lexer when the lexer is of the backtracking persuasion (options.backtrack_lexer = true).
`+this.showPosition(),{text:``,token:null,line:this.yylineno});return this},less:function(e){this.unput(this.match.slice(e))},pastInput:function(){var e=this.matched.substr(0,this.matched.length-this.match.length);return(e.length>20?`...`:``)+e.substr(-20).replace(/\n/g,``)},upcomingInput:function(){var e=this.match;return e.length<20&&(e+=this._input.substr(0,20-e.length)),(e.substr(0,20)+(e.length>20?`...`:``)).replace(/\n/g,``)},showPosition:function(){var e=this.pastInput(),t=Array(e.length+1).join(`-`);return e+this.upcomingInput()+`
`+t+`^`},test_match:function(e,t){var n,r,i;if(this.options.backtrack_lexer&&(i={yylineno:this.yylineno,yylloc:{first_line:this.yylloc.first_line,last_line:this.last_line,first_column:this.yylloc.first_column,last_column:this.yylloc.last_column},yytext:this.yytext,match:this.match,matches:this.matches,matched:this.matched,yyleng:this.yyleng,offset:this.offset,_more:this._more,_input:this._input,yy:this.yy,conditionStack:this.conditionStack.slice(0),done:this.done},this.options.ranges&&(i.yylloc.range=this.yylloc.range.slice(0))),r=e[0].match(/(?:\r\n?|\n).*/g),r&&(this.yylineno+=r.length),this.yylloc={first_line:this.yylloc.last_line,last_line:this.yylineno+1,first_column:this.yylloc.last_column,last_column:r?r[r.length-1].length-r[r.length-1].match(/\r?\n?/)[0].length:this.yylloc.last_column+e[0].length},this.yytext+=e[0],this.match+=e[0],this.matches=e,this.yyleng=this.yytext.length,this.options.ranges&&(this.yylloc.range=[this.offset,this.offset+=this.yyleng]),this._more=!1,this._backtrack=!1,this._input=this._input.slice(e[0].length),this.matched+=e[0],n=this.performAction.call(this,this.yy,this,t,this.conditionStack[this.conditionStack.length-1]),this.done&&this._input&&(this.done=!1),n)return n;if(this._backtrack){for(var a in i)this[a]=i[a];return!1}return!1},next:function(){if(this.done)return this.EOF;this._input||(this.done=!0);var e,t,n,r;this._more||(this.yytext=``,this.match=``);for(var i=this._currentRules(),a=0;a<i.length;a++)if(n=this._input.match(this.rules[i[a]]),n&&(!t||n[0].length>t[0].length)){if(t=n,r=a,this.options.backtrack_lexer){if(e=this.test_match(n,i[a]),e!==!1)return e;if(this._backtrack){t=!1;continue}return!1}if(!this.options.flex)break}return t?(e=this.test_match(t,i[r]),e!==!1&&e):this._input===``?this.EOF:this.parseError(`Lexical error on line `+(this.yylineno+1)+`. Unrecognized text.
`+this.showPosition(),{text:``,token:null,line:this.yylineno})},lex:function(){return this.next()||this.lex()},begin:function(e){this.conditionStack.push(e)},popState:function(){return this.conditionStack.length-1>0?this.conditionStack.pop():this.conditionStack[0]},_currentRules:function(){return this.conditionStack.length&&this.conditionStack[this.conditionStack.length-1]?this.conditions[this.conditionStack[this.conditionStack.length-1]].rules:this.conditions.INITIAL.rules},topState:function(e){return e=this.conditionStack.length-1-Math.abs(e||0),e>=0?this.conditionStack[e]:`INITIAL`},pushState:function(e){this.begin(e)},stateStackSize:function(){return this.conditionStack.length},options:{"case-insensitive":!0},performAction:function(e,t,n,r){switch(n){case 0:return this.begin(`open_directive`),`open_directive`;case 1:return this.begin(`acc_title`),28;case 2:return this.popState(),`acc_title_value`;case 3:return this.begin(`acc_descr`),30;case 4:return this.popState(),`acc_descr_value`;case 5:this.begin(`acc_descr_multiline`);break;case 6:this.popState();break;case 7:return`acc_descr_multiline_value`;case 8:break;case 9:break;case 10:break;case 11:return 10;case 12:break;case 13:break;case 14:this.begin(`href`);break;case 15:this.popState();break;case 16:return 40;case 17:this.begin(`callbackname`);break;case 18:this.popState();break;case 19:this.popState(),this.begin(`callbackargs`);break;case 20:return 38;case 21:this.popState();break;case 22:return 39;case 23:this.begin(`click`);break;case 24:this.popState();break;case 25:return 37;case 26:return 4;case 27:return 19;case 28:return 20;case 29:return 21;case 30:return 22;case 31:return 23;case 32:return 25;case 33:return 24;case 34:return 26;case 35:return 12;case 36:return 13;case 37:return 14;case 38:return 15;case 39:return 16;case 40:return 17;case 41:return 18;case 42:return`date`;case 43:return 27;case 44:return`accDescription`;case 45:return 33;case 46:return 35;case 47:return 36;case 48:return`:`;case 49:return 6;case 50:return`INVALID`}},rules:[/^(?:%%\{)/i,/^(?:accTitle\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*\{\s*)/i,/^(?:[\}])/i,/^(?:[^\}]*)/i,/^(?:%%(?!\{)*[^\n]*)/i,/^(?:[^\}]%%*[^\n]*)/i,/^(?:%%*[^\n]*[\n]*)/i,/^(?:[\n]+)/i,/^(?:\s+)/i,/^(?:%[^\n]*)/i,/^(?:href[\s]+["])/i,/^(?:["])/i,/^(?:[^"]*)/i,/^(?:call[\s]+)/i,/^(?:\([\s]*\))/i,/^(?:\()/i,/^(?:[^(]*)/i,/^(?:\))/i,/^(?:[^)]*)/i,/^(?:click[\s]+)/i,/^(?:[\s\n])/i,/^(?:[^\s\n]*)/i,/^(?:gantt\b)/i,/^(?:dateFormat\s[^#\n;]+)/i,/^(?:inclusiveEndDates\b)/i,/^(?:topAxis\b)/i,/^(?:axisFormat\s[^#\n;]+)/i,/^(?:tickInterval\s[^#\n;]+)/i,/^(?:includes\s[^#\n;]+)/i,/^(?:excludes\s[^#\n;]+)/i,/^(?:todayMarker\s[^\n;]+)/i,/^(?:weekday\s+monday\b)/i,/^(?:weekday\s+tuesday\b)/i,/^(?:weekday\s+wednesday\b)/i,/^(?:weekday\s+thursday\b)/i,/^(?:weekday\s+friday\b)/i,/^(?:weekday\s+saturday\b)/i,/^(?:weekday\s+sunday\b)/i,/^(?:\d\d\d\d-\d\d-\d\d\b)/i,/^(?:title\s[^\n]+)/i,/^(?:accDescription\s[^#\n;]+)/i,/^(?:section\s[^\n]+)/i,/^(?:[^:\n]+)/i,/^(?::[^#\n;]+)/i,/^(?::)/i,/^(?:$)/i,/^(?:.)/i],conditions:{acc_descr_multiline:{rules:[6,7],inclusive:!1},acc_descr:{rules:[4],inclusive:!1},acc_title:{rules:[2],inclusive:!1},callbackargs:{rules:[21,22],inclusive:!1},callbackname:{rules:[18,19,20],inclusive:!1},href:{rules:[15,16],inclusive:!1},click:{rules:[24,25],inclusive:!1},INITIAL:{rules:[0,1,3,5,8,9,10,11,12,13,14,17,23,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50],inclusive:!0}}}}();function T(){this.yy={}}return T.prototype=w,w.Parser=T,new T}();fe.parser=fe;var pe=fe;N.default.extend(le.default),N.default.extend(ue.default),N.default.extend(de.default);var P=``,me=``,he=void 0,F=``,I=[],L=[],R={},z=[],B=[],V=``,H=``,ge=[`active`,`done`,`crit`,`milestone`],U=[],W=!1,G=!1,K=`sunday`,q=0,_e=function(){z=[],B=[],V=``,U=[],qe=0,Xe=void 0,X=void 0,Z=[],P=``,me=``,H=``,he=void 0,F=``,I=[],L=[],W=!1,G=!1,q=0,R={},ae(),K=`sunday`},ve=function(e){me=e},ye=function(){return me},be=function(e){he=e},xe=function(){return he},Se=function(e){F=e},Ce=function(){return F},we=function(e){P=e},Te=function(){W=!0},Ee=function(){return W},De=function(){G=!0},Oe=function(){return G},ke=function(e){H=e},Ae=function(){return H},je=function(){return P},Me=function(e){I=e.toLowerCase().split(/[\s,]+/)},Ne=function(){return I},Pe=function(e){L=e.toLowerCase().split(/[\s,]+/)},Fe=function(){return L},Ie=function(){return R},Le=function(e){V=e,z.push(e)},Re=function(){return z},ze=function(){let e=et(),t=0;for(;!e&&t<10;)e=et(),t++;return B=Z,B},Be=function(e,t,n,r){return r.includes(e.format(t.trim()))?!1:e.isoWeekday()>=6&&n.includes(`weekends`)||n.includes(e.format(`dddd`).toLowerCase())?!0:n.includes(e.format(t.trim()))},Ve=function(e){K=e},He=function(){return K},Ue=function(e,t,n,r){if(!n.length||e.manualEndTime)return;let i;i=e.startTime instanceof Date?(0,N.default)(e.startTime):(0,N.default)(e.startTime,t,!0),i=i.add(1,`d`);let a;a=e.endTime instanceof Date?(0,N.default)(e.endTime):(0,N.default)(e.endTime,t,!0);let[o,s]=We(i,a,t,n,r);e.endTime=o.toDate(),e.renderEndTime=s},We=function(e,t,n,r,i){let a=!1,o=null;for(;e<=t;)a||(o=t.toDate()),a=Be(e,n,r,i),a&&(t=t.add(1,`d`)),e=e.add(1,`d`);return[t,o]},J=function(e,t,n){n=n.trim();let r=/^after\s+(?<ids>[\d\w- ]+)/.exec(n);if(r!==null){let e=null;for(let t of r.groups.ids.split(` `)){let n=Q(t);n!==void 0&&(!e||n.endTime>e.endTime)&&(e=n)}if(e)return e.endTime;let t=new Date;return t.setHours(0,0,0,0),t}let i=(0,N.default)(n,t.trim(),!0);if(i.isValid())return i.toDate();{O.debug(`Invalid date:`+n),O.debug(`With date format:`+t.trim());let e=new Date(n);if(e===void 0||isNaN(e.getTime())||e.getFullYear()<-1e4||e.getFullYear()>1e4)throw Error(`Invalid date:`+n);return e}},Ge=function(e){let t=/^(\d+(?:\.\d+)?)([Mdhmswy]|ms)$/.exec(e.trim());return t===null?[NaN,`ms`]:[Number.parseFloat(t[1]),t[2]]},Ke=function(e,t,n,r=!1){n=n.trim();let i=/^until\s+(?<ids>[\d\w- ]+)/.exec(n);if(i!==null){let e=null;for(let t of i.groups.ids.split(` `)){let n=Q(t);n!==void 0&&(!e||n.startTime<e.startTime)&&(e=n)}if(e)return e.startTime;let t=new Date;return t.setHours(0,0,0,0),t}let a=(0,N.default)(n,t.trim(),!0);if(a.isValid())return r&&(a=a.add(1,`d`)),a.toDate();let o=(0,N.default)(e),[s,c]=Ge(n);if(!Number.isNaN(s)){let e=o.add(s,c);e.isValid()&&(o=e)}return o.toDate()},qe=0,Y=function(e){return e===void 0?(qe+=1,`task`+qe):e},Je=function(e,t){let n;n=t.substr(0,1)===`:`?t.substr(1,t.length):t;let r=n.split(`,`),i={};ot(r,i,ge);for(let e=0;e<r.length;e++)r[e]=r[e].trim();let a=``;switch(r.length){case 1:i.id=Y(),i.startTime=e.endTime,a=r[0];break;case 2:i.id=Y(),i.startTime=J(void 0,P,r[0]),a=r[1];break;case 3:i.id=Y(r[0]),i.startTime=J(void 0,P,r[1]),a=r[2]}return a&&(i.endTime=Ke(i.startTime,P,a,W),i.manualEndTime=(0,N.default)(a,`YYYY-MM-DD`,!0).isValid(),Ue(i,P,L,I)),i},Ye=function(e,t){let n;n=t.substr(0,1)===`:`?t.substr(1,t.length):t;let r=n.split(`,`),i={};ot(r,i,ge);for(let e=0;e<r.length;e++)r[e]=r[e].trim();switch(r.length){case 1:i.id=Y(),i.startTime={type:`prevTaskEnd`,id:e},i.endTime={data:r[0]};break;case 2:i.id=Y(),i.startTime={type:`getStartDate`,startData:r[0]},i.endTime={data:r[1]};break;case 3:i.id=Y(r[0]),i.startTime={type:`getStartDate`,startData:r[1]},i.endTime={data:r[2]}}return i},Xe,X,Z=[],Ze={},Qe=function(e,t){let n={section:V,type:V,processed:!1,manualEndTime:!1,renderEndTime:null,raw:{data:t},task:e,classes:[]},r=Ye(X,t);n.raw.startTime=r.startTime,n.raw.endTime=r.endTime,n.id=r.id,n.prevTaskId=X,n.active=r.active,n.done=r.done,n.crit=r.crit,n.milestone=r.milestone,n.order=q,q++;let i=Z.push(n);X=n.id,Ze[n.id]=i-1},Q=function(e){let t=Ze[e];return Z[t]},$e=function(e,t){let n={section:V,type:V,description:e,task:e,classes:[]},r=Je(Xe,t);n.startTime=r.startTime,n.endTime=r.endTime,n.id=r.id,n.active=r.active,n.done=r.done,n.crit=r.crit,n.milestone=r.milestone,Xe=n,B.push(n)},et=function(){let e=function(e){let t=Z[e],n=``;switch(Z[e].raw.startTime.type){case`prevTaskEnd`:t.startTime=Q(t.prevTaskId).endTime;break;case`getStartDate`:n=J(void 0,P,Z[e].raw.startTime.startData),n&&(Z[e].startTime=n)}return Z[e].startTime&&(Z[e].endTime=Ke(Z[e].startTime,P,Z[e].raw.endTime.data,W),Z[e].endTime&&(Z[e].processed=!0,Z[e].manualEndTime=(0,N.default)(Z[e].raw.endTime.data,`YYYY-MM-DD`,!0).isValid(),Ue(Z[e],P,L,I))),Z[e].processed},t=!0;for(let[n,r]of Z.entries())e(n),t&&=r.processed;return t},tt=function(e,t){let n=t;M().securityLevel!==`loose`&&(n=(0,ce.sanitizeUrl)(t)),e.split(`,`).forEach(function(e){Q(e)!==void 0&&(it(e,()=>{window.open(n,`_self`)}),R[e]=n)}),nt(e,`clickable`)},nt=function(e,t){e.split(`,`).forEach(function(e){let n=Q(e);n!==void 0&&n.classes.push(t)})},rt=function(e,t,n){if(M().securityLevel!==`loose`||t===void 0)return;let r=[];if(typeof n==`string`){r=n.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/);for(let e=0;e<r.length;e++){let t=r[e].trim();t.charAt(0)===`"`&&t.charAt(t.length-1)===`"`&&(t=t.substr(1,t.length-2)),r[e]=t}}r.length===0&&r.push(e),Q(e)!==void 0&&it(e,()=>{se.runFunc(t,...r)})},it=function(e,t){U.push(function(){let n=document.querySelector(`[id="${e}"]`);n!==null&&n.addEventListener(`click`,function(){t()})},function(){let n=document.querySelector(`[id="${e}-text"]`);n!==null&&n.addEventListener(`click`,function(){t()})})},at={getConfig:()=>M().gantt,clear:_e,setDateFormat:we,getDateFormat:je,enableInclusiveEndDates:Te,endDatesAreInclusive:Ee,enableTopAxis:De,topAxisEnabled:Oe,setAxisFormat:ve,getAxisFormat:ye,setTickInterval:be,getTickInterval:xe,setTodayMarker:Se,getTodayMarker:Ce,setAccTitle:j,getAccTitle:te,setDiagramTitle:k,getDiagramTitle:ne,setDisplayMode:ke,getDisplayMode:Ae,setAccDescription:A,getAccDescription:ie,addSection:Le,getSections:Re,getTasks:ze,addTask:Qe,findTaskById:Q,addTaskOrg:$e,setIncludes:Me,getIncludes:Ne,setExcludes:Pe,getExcludes:Fe,setClickEvent:function(e,t,n){e.split(`,`).forEach(function(e){rt(e,t,n)}),nt(e,`clickable`)},setLink:tt,getLinks:Ie,bindFunctions:function(e){U.forEach(function(t){t(e)})},parseDuration:Ge,isInvalidDate:Be,setWeekday:Ve,getWeekday:He};function ot(e,t,n){let r=!0;for(;r;)r=!1,n.forEach(function(n){let i=`^\\s*`+n+`\\s*$`,a=new RegExp(i);e[0].match(a)&&(t[n]=!0,e.shift(1),r=!0)})}var st=function(){O.debug(`Something is calling, setConf, remove the call`)},ct={monday:l,tuesday:d,wednesday:y,thursday:u,friday:x,saturday:h,sunday:C},lt=(e,t)=>{let n=[...e].map(()=>-1/0),r=[...e].sort((e,t)=>e.startTime-t.startTime||e.order-t.order),i=0;for(let e of r)for(let r=0;r<n.length;r++)if(e.startTime>=n[r]){n[r]=e.endTime,e.order=r+t,r>i&&(i=r);break}return i},$,ut={parser:pe,db:at,renderer:{setConf:st,draw:function(e,t,l,u){let d=M().gantt,h=M().securityLevel,_;h===`sandbox`&&(_=n(`#i`+t));let y=n(h===`sandbox`?_.nodes()[0].contentDocument.body:`body`),b=h===`sandbox`?_.nodes()[0].contentDocument:document,x=b.getElementById(t);$=x.parentElement.offsetWidth,$===void 0&&($=1200),d.useWidth!==void 0&&($=d.useWidth);let S=u.db.getTasks(),C=[];for(let e of S)C.push(e.type);C=le(C);let D={},k=2*d.topPadding;if(u.db.getDisplayMode()===`compact`||d.displayMode===`compact`){let e={};for(let t of S)e[t.section]===void 0?e[t.section]=[t]:e[t.section].push(t);let t=0;for(let n of Object.keys(e)){let r=lt(e[n],t)+1;t+=r,k+=r*(d.barHeight+d.barGap),D[n]=r}}else{k+=S.length*(d.barHeight+d.barGap);for(let e of C)D[e]=S.filter(t=>t.type===e).length}x.setAttribute(`viewBox`,`0 0 `+$+` `+k);let A=y.select(`[id="${t}"]`),j=m().domain([a(S,function(e){return e.startTime}),i(S,function(e){return e.endTime})]).rangeRound([0,$-d.leftPadding-d.rightPadding]);function ee(e,t){let n=e.startTime,r=t.startTime,i=0;return n>r?i=1:n<r&&(i=-1),i}S.sort(ee),te(S,$,k),oe(A,k,$,d.useMaxWidth),A.append(`text`).text(u.db.getDiagramTitle()).attr(`x`,$/2).attr(`y`,d.titleTopMargin).attr(`class`,`titleText`);function te(e,t,n){let i=d.barHeight,a=i+d.barGap,o=d.topPadding,s=d.leftPadding,c=r().domain([0,C.length]).range([`#00B9FA`,`#F95002`]).interpolate(E);ie(a,o,s,t,n,e,u.db.getExcludes(),u.db.getIncludes()),ae(s,o,t,n),ne(e,a,o,s,i,c,t),se(a,o),ce(s,o,t,n)}function ne(e,r,i,a,o,s,c){let l=[...new Set(e.map(e=>e.order))].map(t=>e.find(e=>e.order===t));A.append(`g`).selectAll(`rect`).data(l).enter().append(`rect`).attr(`x`,0).attr(`y`,function(e,t){return t=e.order,t*r+i-2}).attr(`width`,function(){return c-d.rightPadding/2}).attr(`height`,r).attr(`class`,function(e){for(let[t,n]of C.entries())if(e.type===n)return`section section`+t%d.numberSectionStyles;return`section section0`});let f=A.append(`g`).selectAll(`rect`).data(e).enter(),p=u.db.getLinks();if(f.append(`rect`).attr(`id`,function(e){return e.id}).attr(`rx`,3).attr(`ry`,3).attr(`x`,function(e){return e.milestone?j(e.startTime)+a+.5*(j(e.endTime)-j(e.startTime))-.5*o:j(e.startTime)+a}).attr(`y`,function(e,t){return t=e.order,t*r+i}).attr(`width`,function(e){return e.milestone?o:j(e.renderEndTime||e.endTime)-j(e.startTime)}).attr(`height`,o).attr(`transform-origin`,function(e,t){return t=e.order,(j(e.startTime)+a+.5*(j(e.endTime)-j(e.startTime))).toString()+`px `+(t*r+i+.5*o).toString()+`px`}).attr(`class`,function(e){let t=``;e.classes.length>0&&(t=e.classes.join(` `));let n=0;for(let[t,r]of C.entries())e.type===r&&(n=t%d.numberSectionStyles);let r=``;return e.active?e.crit?r+=` activeCrit`:r=` active`:e.done?r=e.crit?` doneCrit`:` done`:e.crit&&(r+=` crit`),r.length===0&&(r=` task`),e.milestone&&(r=` milestone `+r),r+=n,r+=` `+t,`task`+r}),f.append(`text`).attr(`id`,function(e){return e.id+`-text`}).text(function(e){return e.task}).attr(`font-size`,d.fontSize).attr(`x`,function(e){let t=j(e.startTime),n=j(e.renderEndTime||e.endTime);e.milestone&&(t+=.5*(j(e.endTime)-j(e.startTime))-.5*o),e.milestone&&(n=t+o);let r=this.getBBox().width;return r>n-t?n+r+1.5*d.leftPadding>c?t+a-5:n+a+5:(n-t)/2+t+a}).attr(`y`,function(e,t){return t=e.order,t*r+d.barHeight/2+(d.fontSize/2-2)+i}).attr(`text-height`,o).attr(`class`,function(e){let t=j(e.startTime),n=j(e.endTime);e.milestone&&(n=t+o);let r=this.getBBox().width,i=``;e.classes.length>0&&(i=e.classes.join(` `));let a=0;for(let[t,n]of C.entries())e.type===n&&(a=t%d.numberSectionStyles);let s=``;return e.active&&(s=e.crit?`activeCritText`+a:`activeText`+a),e.done?s=e.crit?s+` doneCritText`+a:s+` doneText`+a:e.crit&&(s=s+` critText`+a),e.milestone&&(s+=` milestoneText`),r>n-t?n+r+1.5*d.leftPadding>c?i+` taskTextOutsideLeft taskTextOutside`+a+` `+s:i+` taskTextOutsideRight taskTextOutside`+a+` `+s+` width-`+r:i+` taskText taskText`+a+` `+s+` width-`+r}),M().securityLevel===`sandbox`){let e;e=n(`#i`+t);let r=e.nodes()[0].contentDocument;f.filter(function(e){return p[e.id]!==void 0}).each(function(e){var t=r.querySelector(`#`+e.id),n=r.querySelector(`#`+e.id+`-text`);let i=t.parentNode;var a=r.createElement(`a`);a.setAttribute(`xlink:href`,p[e.id]),a.setAttribute(`target`,`_top`),i.appendChild(a),a.appendChild(t),a.appendChild(n)})}}function ie(e,t,n,r,i,a,o,s){if(o.length===0&&s.length===0)return;let c,l;for(let{startTime:e,endTime:t}of a)(c===void 0||e<c)&&(c=e),(l===void 0||t>l)&&(l=t);if(!c||!l)return;if((0,N.default)(l).diff((0,N.default)(c),`year`)>5){O.warn(`The difference between the min and max time is more than 5 years. This will cause performance issues. Skipping drawing exclude days.`);return}let f=u.db.getDateFormat(),p=[],m=null,h=(0,N.default)(c);for(;h.valueOf()<=l;)u.db.isInvalidDate(h,f,o,s)?m?m.end=h:m={start:h,end:h}:m&&=(p.push(m),null),h=h.add(1,`d`);A.append(`g`).selectAll(`rect`).data(p).enter().append(`rect`).attr(`id`,function(e){return`exclude-`+e.start.format(`YYYY-MM-DD`)}).attr(`x`,function(e){return j(e.start)+n}).attr(`y`,d.gridLineStartPadding).attr(`width`,function(e){let t=e.end.add(1,`day`);return j(t)-j(e.start)}).attr(`height`,i-t-d.gridLineStartPadding).attr(`transform-origin`,function(t,r){return(j(t.start)+n+.5*(j(t.end)-j(t.start))).toString()+`px `+(r*e+.5*i).toString()+`px`}).attr(`class`,`exclude-range`)}function ae(e,t,n,r){let i=c(j).tickSize(-r+t+d.gridLineStartPadding).tickFormat(s(u.db.getAxisFormat()||d.axisFormat||`%Y-%m-%d`)),a=/^([1-9]\d*)(millisecond|second|minute|hour|day|week|month)$/.exec(u.db.getTickInterval()||d.tickInterval);if(a!==null){let e=a[1],t=a[2],n=u.db.getWeekday()||d.weekday;switch(t){case`millisecond`:i.ticks(w.every(e));break;case`second`:i.ticks(o.every(e));break;case`minute`:i.ticks(f.every(e));break;case`hour`:i.ticks(p.every(e));break;case`day`:i.ticks(g.every(e));break;case`week`:i.ticks(ct[n].every(e));break;case`month`:i.ticks(v.every(e))}}if(A.append(`g`).attr(`class`,`grid`).attr(`transform`,`translate(`+e+`, `+(r-50)+`)`).call(i).selectAll(`text`).style(`text-anchor`,`middle`).attr(`fill`,`#000`).attr(`stroke`,`none`).attr(`font-size`,10).attr(`dy`,`1em`),u.db.topAxisEnabled()||d.topAxis){let n=T(j).tickSize(-r+t+d.gridLineStartPadding).tickFormat(s(u.db.getAxisFormat()||d.axisFormat||`%Y-%m-%d`));if(a!==null){let e=a[1],t=a[2],r=u.db.getWeekday()||d.weekday;switch(t){case`millisecond`:n.ticks(w.every(e));break;case`second`:n.ticks(o.every(e));break;case`minute`:n.ticks(f.every(e));break;case`hour`:n.ticks(p.every(e));break;case`day`:n.ticks(g.every(e));break;case`week`:n.ticks(ct[r].every(e));break;case`month`:n.ticks(v.every(e))}}A.append(`g`).attr(`class`,`grid`).attr(`transform`,`translate(`+e+`, `+t+`)`).call(n).selectAll(`text`).style(`text-anchor`,`middle`).attr(`fill`,`#000`).attr(`stroke`,`none`).attr(`font-size`,10)}}function se(e,t){let n=0,r=Object.keys(D).map(e=>[e,D[e]]);A.append(`g`).selectAll(`text`).data(r).enter().append(function(e){let t=e[0].split(re.lineBreakRegex),n=-(t.length-1)/2,r=b.createElementNS(`http://www.w3.org/2000/svg`,`text`);r.setAttribute(`dy`,n+`em`);for(let[e,n]of t.entries()){let t=b.createElementNS(`http://www.w3.org/2000/svg`,`tspan`);t.setAttribute(`alignment-baseline`,`central`),t.setAttribute(`x`,`10`),e>0&&t.setAttribute(`dy`,`1em`),t.textContent=n,r.appendChild(t)}return r}).attr(`x`,10).attr(`y`,function(i,a){if(a>0)for(let o=0;o<a;o++)return n+=r[a-1][1],i[1]*e/2+n*e+t;else return i[1]*e/2+t}).attr(`font-size`,d.sectionFontSize).attr(`class`,function(e){for(let[t,n]of C.entries())if(e[0]===n)return`sectionTitle sectionTitle`+t%d.numberSectionStyles;return`sectionTitle`})}function ce(e,t,n,r){let i=u.db.getTodayMarker();if(i===`off`)return;let a=A.append(`g`).attr(`class`,`today`),o=new Date,s=a.append(`line`);s.attr(`x1`,j(o)+e).attr(`x2`,j(o)+e).attr(`y1`,d.titleTopMargin).attr(`y2`,r-d.titleTopMargin).attr(`class`,`today`),i!==``&&s.attr(`style`,i.replace(/,/g,`;`))}function le(e){let t={},n=[];for(let r=0,i=e.length;r<i;++r)Object.prototype.hasOwnProperty.call(t,e[r])||(t[e[r]]=!0,n.push(e[r]));return n}}},styles:e=>`
  .mermaid-main-font {
    font-family: var(--mermaid-font-family, "trebuchet ms", verdana, arial, sans-serif);
  }

  .exclude-range {
    fill: ${e.excludeBkgColor};
  }

  .section {
    stroke: none;
    opacity: 0.2;
  }

  .section0 {
    fill: ${e.sectionBkgColor};
  }

  .section2 {
    fill: ${e.sectionBkgColor2};
  }

  .section1,
  .section3 {
    fill: ${e.altSectionBkgColor};
    opacity: 0.2;
  }

  .sectionTitle0 {
    fill: ${e.titleColor};
  }

  .sectionTitle1 {
    fill: ${e.titleColor};
  }

  .sectionTitle2 {
    fill: ${e.titleColor};
  }

  .sectionTitle3 {
    fill: ${e.titleColor};
  }

  .sectionTitle {
    text-anchor: start;
    font-family: var(--mermaid-font-family, "trebuchet ms", verdana, arial, sans-serif);
  }


  /* Grid and axis */

  .grid .tick {
    stroke: ${e.gridColor};
    opacity: 0.8;
    shape-rendering: crispEdges;
  }

  .grid .tick text {
    font-family: ${e.fontFamily};
    fill: ${e.textColor};
  }

  .grid path {
    stroke-width: 0;
  }


  /* Today line */

  .today {
    fill: none;
    stroke: ${e.todayLineColor};
    stroke-width: 2px;
  }


  /* Task styling */

  /* Default task */

  .task {
    stroke-width: 2;
  }

  .taskText {
    text-anchor: middle;
    font-family: var(--mermaid-font-family, "trebuchet ms", verdana, arial, sans-serif);
  }

  .taskTextOutsideRight {
    fill: ${e.taskTextDarkColor};
    text-anchor: start;
    font-family: var(--mermaid-font-family, "trebuchet ms", verdana, arial, sans-serif);
  }

  .taskTextOutsideLeft {
    fill: ${e.taskTextDarkColor};
    text-anchor: end;
  }


  /* Special case clickable */

  .task.clickable {
    cursor: pointer;
  }

  .taskText.clickable {
    cursor: pointer;
    fill: ${e.taskTextClickableColor} !important;
    font-weight: bold;
  }

  .taskTextOutsideLeft.clickable {
    cursor: pointer;
    fill: ${e.taskTextClickableColor} !important;
    font-weight: bold;
  }

  .taskTextOutsideRight.clickable {
    cursor: pointer;
    fill: ${e.taskTextClickableColor} !important;
    font-weight: bold;
  }


  /* Specific task settings for the sections*/

  .taskText0,
  .taskText1,
  .taskText2,
  .taskText3 {
    fill: ${e.taskTextColor};
  }

  .task0,
  .task1,
  .task2,
  .task3 {
    fill: ${e.taskBkgColor};
    stroke: ${e.taskBorderColor};
  }

  .taskTextOutside0,
  .taskTextOutside2
  {
    fill: ${e.taskTextOutsideColor};
  }

  .taskTextOutside1,
  .taskTextOutside3 {
    fill: ${e.taskTextOutsideColor};
  }


  /* Active task */

  .active0,
  .active1,
  .active2,
  .active3 {
    fill: ${e.activeTaskBkgColor};
    stroke: ${e.activeTaskBorderColor};
  }

  .activeText0,
  .activeText1,
  .activeText2,
  .activeText3 {
    fill: ${e.taskTextDarkColor} !important;
  }


  /* Completed task */

  .done0,
  .done1,
  .done2,
  .done3 {
    stroke: ${e.doneTaskBorderColor};
    fill: ${e.doneTaskBkgColor};
    stroke-width: 2;
  }

  .doneText0,
  .doneText1,
  .doneText2,
  .doneText3 {
    fill: ${e.taskTextDarkColor} !important;
  }


  /* Tasks on the critical line */

  .crit0,
  .crit1,
  .crit2,
  .crit3 {
    stroke: ${e.critBorderColor};
    fill: ${e.critBkgColor};
    stroke-width: 2;
  }

  .activeCrit0,
  .activeCrit1,
  .activeCrit2,
  .activeCrit3 {
    stroke: ${e.critBorderColor};
    fill: ${e.activeTaskBkgColor};
    stroke-width: 2;
  }

  .doneCrit0,
  .doneCrit1,
  .doneCrit2,
  .doneCrit3 {
    stroke: ${e.critBorderColor};
    fill: ${e.doneTaskBkgColor};
    stroke-width: 2;
    cursor: pointer;
    shape-rendering: crispEdges;
  }

  .milestone {
    transform: rotate(45deg) scale(0.8,0.8);
  }

  .milestoneText {
    font-style: italic;
  }
  .doneCritText0,
  .doneCritText1,
  .doneCritText2,
  .doneCritText3 {
    fill: ${e.taskTextDarkColor} !important;
  }

  .activeCritText0,
  .activeCritText1,
  .activeCritText2,
  .activeCritText3 {
    fill: ${e.taskTextDarkColor} !important;
  }

  .titleText {
    text-anchor: middle;
    font-size: 18px;
    fill: ${e.titleColor||e.textColor};
    font-family: var(--mermaid-font-family, "trebuchet ms", verdana, arial, sans-serif);
  }
`};export{ut as diagram};