import{a as e}from"./rolldown-runtime-Dqfqb5bO.js";import{_ as t,p as n}from"./src-B_EVwkEo.js";import{n as r,r as i}from"./chunk-AGHRB4JF-vywctk_i.js";import{B as a,C as o,U as s,_ as c,a as l,b as u,c as d,s as f,v as p,z as m}from"./chunk-ABZYJK2D-VN4LS1pm.js";import{t as h}from"./linear-Dz14sTxM.js";import{C as g,S as _,_ as v,a as y,b,c as x,d as S,f as C,g as w,h as T,i as E,l as D,m as O,n as k,o as A,p as j,r as M,s as ee,t as te,u as ne,v as re,x as ie,y as ae}from"./advancedFormat-Ci0lZjOs.js";import{t as N}from"./dist-DRdtc2aQ.js";import{h as P}from"./chunk-S3R3BYOJ-CDIwQNce.js";var F=N(),I=e(t(),1),oe=e(M(),1),se=e(k(),1),ce=e(te(),1),le=(function(){var e=r(function(e,t,n,r){for(n||={},r=e.length;r--;n[e[r]]=t);return n},`o`),t=[6,8,10,12,13,14,15,16,17,18,20,21,22,23,24,25,26,27,28,29,30,31,33,35,36,38,40],n=[1,26],i=[1,27],a=[1,28],o=[1,29],s=[1,30],c=[1,31],l=[1,32],u=[1,33],d=[1,34],f=[1,9],p=[1,10],m=[1,11],h=[1,12],g=[1,13],_=[1,14],v=[1,15],y=[1,16],b=[1,19],x=[1,20],S=[1,21],C=[1,22],w=[1,23],T=[1,25],E=[1,35],D={trace:r(function(){},`trace`),yy:{},symbols_:{error:2,start:3,gantt:4,document:5,EOF:6,line:7,SPACE:8,statement:9,NL:10,weekday:11,weekday_monday:12,weekday_tuesday:13,weekday_wednesday:14,weekday_thursday:15,weekday_friday:16,weekday_saturday:17,weekday_sunday:18,weekend:19,weekend_friday:20,weekend_saturday:21,dateFormat:22,inclusiveEndDates:23,topAxis:24,axisFormat:25,tickInterval:26,excludes:27,includes:28,todayMarker:29,title:30,acc_title:31,acc_title_value:32,acc_descr:33,acc_descr_value:34,acc_descr_multiline_value:35,section:36,clickStatement:37,taskTxt:38,taskData:39,click:40,callbackname:41,callbackargs:42,href:43,clickStatementDebug:44,$accept:0,$end:1},terminals_:{2:`error`,4:`gantt`,6:`EOF`,8:`SPACE`,10:`NL`,12:`weekday_monday`,13:`weekday_tuesday`,14:`weekday_wednesday`,15:`weekday_thursday`,16:`weekday_friday`,17:`weekday_saturday`,18:`weekday_sunday`,20:`weekend_friday`,21:`weekend_saturday`,22:`dateFormat`,23:`inclusiveEndDates`,24:`topAxis`,25:`axisFormat`,26:`tickInterval`,27:`excludes`,28:`includes`,29:`todayMarker`,30:`title`,31:`acc_title`,32:`acc_title_value`,33:`acc_descr`,34:`acc_descr_value`,35:`acc_descr_multiline_value`,36:`section`,38:`taskTxt`,39:`taskData`,40:`click`,41:`callbackname`,42:`callbackargs`,43:`href`},productions_:[0,[3,3],[5,0],[5,2],[7,2],[7,1],[7,1],[7,1],[11,1],[11,1],[11,1],[11,1],[11,1],[11,1],[11,1],[19,1],[19,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,2],[9,2],[9,1],[9,1],[9,1],[9,2],[37,2],[37,3],[37,3],[37,4],[37,3],[37,4],[37,2],[44,2],[44,3],[44,3],[44,4],[44,3],[44,4],[44,2]],performAction:r(function(e,t,n,r,i,a,o){var s=a.length-1;switch(i){case 1:return a[s-1];case 2:this.$=[];break;case 3:a[s-1].push(a[s]),this.$=a[s-1];break;case 4:case 5:this.$=a[s];break;case 6:case 7:this.$=[];break;case 8:r.setWeekday(`monday`);break;case 9:r.setWeekday(`tuesday`);break;case 10:r.setWeekday(`wednesday`);break;case 11:r.setWeekday(`thursday`);break;case 12:r.setWeekday(`friday`);break;case 13:r.setWeekday(`saturday`);break;case 14:r.setWeekday(`sunday`);break;case 15:r.setWeekend(`friday`);break;case 16:r.setWeekend(`saturday`);break;case 17:r.setDateFormat(a[s].substr(11)),this.$=a[s].substr(11);break;case 18:r.enableInclusiveEndDates(),this.$=a[s].substr(18);break;case 19:r.TopAxis(),this.$=a[s].substr(8);break;case 20:r.setAxisFormat(a[s].substr(11)),this.$=a[s].substr(11);break;case 21:r.setTickInterval(a[s].substr(13)),this.$=a[s].substr(13);break;case 22:r.setExcludes(a[s].substr(9)),this.$=a[s].substr(9);break;case 23:r.setIncludes(a[s].substr(9)),this.$=a[s].substr(9);break;case 24:r.setTodayMarker(a[s].substr(12)),this.$=a[s].substr(12);break;case 27:r.setDiagramTitle(a[s].substr(6)),this.$=a[s].substr(6);break;case 28:this.$=a[s].trim(),r.setAccTitle(this.$);break;case 29:case 30:this.$=a[s].trim(),r.setAccDescription(this.$);break;case 31:r.addSection(a[s].substr(8)),this.$=a[s].substr(8);break;case 33:r.addTask(a[s-1],a[s]),this.$=`task`;break;case 34:this.$=a[s-1],r.setClickEvent(a[s-1],a[s],null);break;case 35:this.$=a[s-2],r.setClickEvent(a[s-2],a[s-1],a[s]);break;case 36:this.$=a[s-2],r.setClickEvent(a[s-2],a[s-1],null),r.setLink(a[s-2],a[s]);break;case 37:this.$=a[s-3],r.setClickEvent(a[s-3],a[s-2],a[s-1]),r.setLink(a[s-3],a[s]);break;case 38:this.$=a[s-2],r.setClickEvent(a[s-2],a[s],null),r.setLink(a[s-2],a[s-1]);break;case 39:this.$=a[s-3],r.setClickEvent(a[s-3],a[s-1],a[s]),r.setLink(a[s-3],a[s-2]);break;case 40:this.$=a[s-1],r.setLink(a[s-1],a[s]);break;case 41:case 47:this.$=a[s-1]+` `+a[s];break;case 42:case 43:case 45:this.$=a[s-2]+` `+a[s-1]+` `+a[s];break;case 44:case 46:this.$=a[s-3]+` `+a[s-2]+` `+a[s-1]+` `+a[s]}},`anonymous`),table:[{3:1,4:[1,2]},{1:[3]},e(t,[2,2],{5:3}),{6:[1,4],7:5,8:[1,6],9:7,10:[1,8],11:17,12:n,13:i,14:a,15:o,16:s,17:c,18:l,19:18,20:u,21:d,22:f,23:p,24:m,25:h,26:g,27:_,28:v,29:y,30:b,31:x,33:S,35:C,36:w,37:24,38:T,40:E},e(t,[2,7],{1:[2,1]}),e(t,[2,3]),{9:36,11:17,12:n,13:i,14:a,15:o,16:s,17:c,18:l,19:18,20:u,21:d,22:f,23:p,24:m,25:h,26:g,27:_,28:v,29:y,30:b,31:x,33:S,35:C,36:w,37:24,38:T,40:E},e(t,[2,5]),e(t,[2,6]),e(t,[2,17]),e(t,[2,18]),e(t,[2,19]),e(t,[2,20]),e(t,[2,21]),e(t,[2,22]),e(t,[2,23]),e(t,[2,24]),e(t,[2,25]),e(t,[2,26]),e(t,[2,27]),{32:[1,37]},{34:[1,38]},e(t,[2,30]),e(t,[2,31]),e(t,[2,32]),{39:[1,39]},e(t,[2,8]),e(t,[2,9]),e(t,[2,10]),e(t,[2,11]),e(t,[2,12]),e(t,[2,13]),e(t,[2,14]),e(t,[2,15]),e(t,[2,16]),{41:[1,40],43:[1,41]},e(t,[2,4]),e(t,[2,28]),e(t,[2,29]),e(t,[2,33]),e(t,[2,34],{42:[1,42],43:[1,43]}),e(t,[2,40],{41:[1,44]}),e(t,[2,35],{43:[1,45]}),e(t,[2,36]),e(t,[2,38],{42:[1,46]}),e(t,[2,37]),e(t,[2,39])],defaultActions:{},parseError:r(function(e,t){if(t.recoverable)this.trace(e);else{var n=Error(e);throw n.hash=t,n}},`parseError`),parse:r(function(e){var t=this,n=[0],i=[],a=[null],o=[],s=this.table,c=``,l=0,u=0,d=0,f=2,p=1,m=o.slice.call(arguments,1),h=Object.create(this.lexer),g={yy:{}};for(var _ in this.yy)Object.prototype.hasOwnProperty.call(this.yy,_)&&(g.yy[_]=this.yy[_]);h.setInput(e,g.yy),g.yy.lexer=h,g.yy.parser=this,h.yylloc===void 0&&(h.yylloc={});var v=h.yylloc;o.push(v);var y=h.options&&h.options.ranges;this.parseError=typeof g.yy.parseError==`function`?g.yy.parseError:Object.getPrototypeOf(this).parseError;function b(e){n.length-=2*e,a.length-=e,o.length-=e}r(b,`popStack`);function x(){var e=i.pop()||h.lex()||p;return typeof e!=`number`&&(e instanceof Array&&(i=e,e=i.pop()),e=t.symbols_[e]||e),e}r(x,`lex`);for(var S,C,w,T,E,D={},O,k,A,j;;){if(w=n[n.length-1],this.defaultActions[w]?T=this.defaultActions[w]:(S??=x(),T=s[w]&&s[w][S]),T===void 0||!T.length||!T[0]){var M=``;for(O in j=[],s[w])this.terminals_[O]&&O>f&&j.push(`'`+this.terminals_[O]+`'`);M=h.showPosition?`Parse error on line `+(l+1)+`:
`+h.showPosition()+`
Expecting `+j.join(`, `)+`, got '`+(this.terminals_[S]||S)+`'`:`Parse error on line `+(l+1)+`: Unexpected `+(S==p?`end of input`:`'`+(this.terminals_[S]||S)+`'`),this.parseError(M,{text:h.match,token:this.terminals_[S]||S,line:h.yylineno,loc:v,expected:j})}if(T[0]instanceof Array&&T.length>1)throw Error(`Parse Error: multiple actions possible at state: `+w+`, token: `+S);switch(T[0]){case 1:n.push(S),a.push(h.yytext),o.push(h.yylloc),n.push(T[1]),S=null,C?(S=C,C=null):(u=h.yyleng,c=h.yytext,l=h.yylineno,v=h.yylloc,d>0&&d--);break;case 2:if(k=this.productions_[T[1]][1],D.$=a[a.length-k],D._$={first_line:o[o.length-(k||1)].first_line,last_line:o[o.length-1].last_line,first_column:o[o.length-(k||1)].first_column,last_column:o[o.length-1].last_column},y&&(D._$.range=[o[o.length-(k||1)].range[0],o[o.length-1].range[1]]),E=this.performAction.apply(D,[c,u,l,g.yy,T[1],a,o].concat(m)),E!==void 0)return E;k&&(n=n.slice(0,-1*k*2),a=a.slice(0,-1*k),o=o.slice(0,-1*k)),n.push(this.productions_[T[1]][0]),a.push(D.$),o.push(D._$),A=s[n[n.length-2]][n[n.length-1]],n.push(A);break;case 3:return!0}}return!0},`parse`)};D.lexer=(function(){return{EOF:1,parseError:r(function(e,t){if(this.yy.parser)this.yy.parser.parseError(e,t);else throw Error(e)},`parseError`),setInput:r(function(e,t){return this.yy=t||this.yy||{},this._input=e,this._more=this._backtrack=this.done=!1,this.yylineno=this.yyleng=0,this.yytext=this.matched=this.match=``,this.conditionStack=[`INITIAL`],this.yylloc={first_line:1,first_column:0,last_line:1,last_column:0},this.options.ranges&&(this.yylloc.range=[0,0]),this.offset=0,this},`setInput`),input:r(function(){var e=this._input[0];return this.yytext+=e,this.yyleng++,this.offset++,this.match+=e,this.matched+=e,e.match(/(?:\r\n?|\n).*/g)?(this.yylineno++,this.yylloc.last_line++):this.yylloc.last_column++,this.options.ranges&&this.yylloc.range[1]++,this._input=this._input.slice(1),e},`input`),unput:r(function(e){var t=e.length,n=e.split(/(?:\r\n?|\n)/g);this._input=e+this._input,this.yytext=this.yytext.substr(0,this.yytext.length-t),this.offset-=t;var r=this.match.split(/(?:\r\n?|\n)/g);this.match=this.match.substr(0,this.match.length-1),this.matched=this.matched.substr(0,this.matched.length-1),n.length-1&&(this.yylineno-=n.length-1);var i=this.yylloc.range;return this.yylloc={first_line:this.yylloc.first_line,last_line:this.yylineno+1,first_column:this.yylloc.first_column,last_column:n?(n.length===r.length?this.yylloc.first_column:0)+r[r.length-n.length].length-n[0].length:this.yylloc.first_column-t},this.options.ranges&&(this.yylloc.range=[i[0],i[0]+this.yyleng-t]),this.yyleng=this.yytext.length,this},`unput`),more:r(function(){return this._more=!0,this},`more`),reject:r(function(){if(this.options.backtrack_lexer)this._backtrack=!0;else return this.parseError(`Lexical error on line `+(this.yylineno+1)+`. You can only invoke reject() in the lexer when the lexer is of the backtracking persuasion (options.backtrack_lexer = true).
`+this.showPosition(),{text:``,token:null,line:this.yylineno});return this},`reject`),less:r(function(e){this.unput(this.match.slice(e))},`less`),pastInput:r(function(){var e=this.matched.substr(0,this.matched.length-this.match.length);return(e.length>20?`...`:``)+e.substr(-20).replace(/\n/g,``)},`pastInput`),upcomingInput:r(function(){var e=this.match;return e.length<20&&(e+=this._input.substr(0,20-e.length)),(e.substr(0,20)+(e.length>20?`...`:``)).replace(/\n/g,``)},`upcomingInput`),showPosition:r(function(){var e=this.pastInput(),t=Array(e.length+1).join(`-`);return e+this.upcomingInput()+`
`+t+`^`},`showPosition`),test_match:r(function(e,t){var n,r,i;if(this.options.backtrack_lexer&&(i={yylineno:this.yylineno,yylloc:{first_line:this.yylloc.first_line,last_line:this.last_line,first_column:this.yylloc.first_column,last_column:this.yylloc.last_column},yytext:this.yytext,match:this.match,matches:this.matches,matched:this.matched,yyleng:this.yyleng,offset:this.offset,_more:this._more,_input:this._input,yy:this.yy,conditionStack:this.conditionStack.slice(0),done:this.done},this.options.ranges&&(i.yylloc.range=this.yylloc.range.slice(0))),r=e[0].match(/(?:\r\n?|\n).*/g),r&&(this.yylineno+=r.length),this.yylloc={first_line:this.yylloc.last_line,last_line:this.yylineno+1,first_column:this.yylloc.last_column,last_column:r?r[r.length-1].length-r[r.length-1].match(/\r?\n?/)[0].length:this.yylloc.last_column+e[0].length},this.yytext+=e[0],this.match+=e[0],this.matches=e,this.yyleng=this.yytext.length,this.options.ranges&&(this.yylloc.range=[this.offset,this.offset+=this.yyleng]),this._more=!1,this._backtrack=!1,this._input=this._input.slice(e[0].length),this.matched+=e[0],n=this.performAction.call(this,this.yy,this,t,this.conditionStack[this.conditionStack.length-1]),this.done&&this._input&&(this.done=!1),n)return n;if(this._backtrack){for(var a in i)this[a]=i[a];return!1}return!1},`test_match`),next:r(function(){if(this.done)return this.EOF;this._input||(this.done=!0);var e,t,n,r;this._more||(this.yytext=``,this.match=``);for(var i=this._currentRules(),a=0;a<i.length;a++)if(n=this._input.match(this.rules[i[a]]),n&&(!t||n[0].length>t[0].length)){if(t=n,r=a,this.options.backtrack_lexer){if(e=this.test_match(n,i[a]),e!==!1)return e;if(this._backtrack){t=!1;continue}return!1}if(!this.options.flex)break}return t?(e=this.test_match(t,i[r]),e!==!1&&e):this._input===``?this.EOF:this.parseError(`Lexical error on line `+(this.yylineno+1)+`. Unrecognized text.
`+this.showPosition(),{text:``,token:null,line:this.yylineno})},`next`),lex:r(function(){return this.next()||this.lex()},`lex`),begin:r(function(e){this.conditionStack.push(e)},`begin`),popState:r(function(){return this.conditionStack.length-1>0?this.conditionStack.pop():this.conditionStack[0]},`popState`),_currentRules:r(function(){return this.conditionStack.length&&this.conditionStack[this.conditionStack.length-1]?this.conditions[this.conditionStack[this.conditionStack.length-1]].rules:this.conditions.INITIAL.rules},`_currentRules`),topState:r(function(e){return e=this.conditionStack.length-1-Math.abs(e||0),e>=0?this.conditionStack[e]:`INITIAL`},`topState`),pushState:r(function(e){this.begin(e)},`pushState`),stateStackSize:r(function(){return this.conditionStack.length},`stateStackSize`),options:{"case-insensitive":!0},performAction:r(function(e,t,n,r){switch(n){case 0:return this.begin(`open_directive`),`open_directive`;case 1:return this.begin(`acc_title`),31;case 2:return this.popState(),`acc_title_value`;case 3:return this.begin(`acc_descr`),33;case 4:return this.popState(),`acc_descr_value`;case 5:this.begin(`acc_descr_multiline`);break;case 6:this.popState();break;case 7:return`acc_descr_multiline_value`;case 8:break;case 9:break;case 10:break;case 11:return 10;case 12:break;case 13:break;case 14:this.begin(`href`);break;case 15:this.popState();break;case 16:return 43;case 17:this.begin(`callbackname`);break;case 18:this.popState();break;case 19:this.popState(),this.begin(`callbackargs`);break;case 20:return 41;case 21:this.popState();break;case 22:return 42;case 23:this.begin(`click`);break;case 24:this.popState();break;case 25:return 40;case 26:return 4;case 27:return 22;case 28:return 23;case 29:return 24;case 30:return 25;case 31:return 26;case 32:return 28;case 33:return 27;case 34:return 29;case 35:return 12;case 36:return 13;case 37:return 14;case 38:return 15;case 39:return 16;case 40:return 17;case 41:return 18;case 42:return 20;case 43:return 21;case 44:return`date`;case 45:return 30;case 46:return`accDescription`;case 47:return 36;case 48:return 38;case 49:return 39;case 50:return`:`;case 51:return 6;case 52:return`INVALID`}},`anonymous`),rules:[/^(?:%%\{)/i,/^(?:accTitle\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*\{\s*)/i,/^(?:[\}])/i,/^(?:[^\}]*)/i,/^(?:%%(?!\{)*[^\n]*)/i,/^(?:[^\}]%%*[^\n]*)/i,/^(?:%%*[^\n]*[\n]*)/i,/^(?:[\n]+)/i,/^(?:\s+)/i,/^(?:%[^\n]*)/i,/^(?:href[\s]+["])/i,/^(?:["])/i,/^(?:[^"]*)/i,/^(?:call[\s]+)/i,/^(?:\([\s]*\))/i,/^(?:\()/i,/^(?:[^(]*)/i,/^(?:\))/i,/^(?:[^)]*)/i,/^(?:click[\s]+)/i,/^(?:[\s\n])/i,/^(?:[^\s\n]*)/i,/^(?:gantt\b)/i,/^(?:dateFormat\s[^#\n;]+)/i,/^(?:inclusiveEndDates\b)/i,/^(?:topAxis\b)/i,/^(?:axisFormat\s[^#\n;]+)/i,/^(?:tickInterval\s[^#\n;]+)/i,/^(?:includes\s[^#\n;]+)/i,/^(?:excludes\s[^#\n;]+)/i,/^(?:todayMarker\s[^\n;]+)/i,/^(?:weekday\s+monday\b)/i,/^(?:weekday\s+tuesday\b)/i,/^(?:weekday\s+wednesday\b)/i,/^(?:weekday\s+thursday\b)/i,/^(?:weekday\s+friday\b)/i,/^(?:weekday\s+saturday\b)/i,/^(?:weekday\s+sunday\b)/i,/^(?:weekend\s+friday\b)/i,/^(?:weekend\s+saturday\b)/i,/^(?:\d\d\d\d-\d\d-\d\d\b)/i,/^(?:title\s[^\n]+)/i,/^(?:accDescription\s[^#\n;]+)/i,/^(?:section\s[^\n]+)/i,/^(?:[^:\n]+)/i,/^(?::[^#\n;]+)/i,/^(?::)/i,/^(?:$)/i,/^(?:.)/i],conditions:{acc_descr_multiline:{rules:[6,7],inclusive:!1},acc_descr:{rules:[4],inclusive:!1},acc_title:{rules:[2],inclusive:!1},callbackargs:{rules:[21,22],inclusive:!1},callbackname:{rules:[18,19,20],inclusive:!1},href:{rules:[15,16],inclusive:!1},click:{rules:[24,25],inclusive:!1},INITIAL:{rules:[0,1,3,5,8,9,10,11,12,13,14,17,23,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52],inclusive:!0}}}})();function O(){this.yy={}}return r(O,`Parser`),O.prototype=D,D.Parser=O,new O})();le.parser=le;var ue=le;I.default.extend(oe.default),I.default.extend(se.default),I.default.extend(ce.default);var de={friday:5,saturday:6},L=``,fe=``,pe=void 0,me=``,R=[],z=[],B=new Map,V=[],H=[],U=``,W=``,he=[`active`,`done`,`crit`,`milestone`,`vert`],G=[],K=!1,ge=!1,_e=`sunday`,q=`saturday`,ve=0,ye=r(function(){V=[],H=[],U=``,G=[],J=0,$e=void 0,X=void 0,Z=[],L=``,fe=``,W=``,pe=void 0,me=``,R=[],z=[],K=!1,ge=!1,ve=0,B=new Map,l(),_e=`sunday`,q=`saturday`},`clear`),be=r(function(e){fe=e},`setAxisFormat`),xe=r(function(){return fe},`getAxisFormat`),Se=r(function(e){pe=e},`setTickInterval`),Ce=r(function(){return pe},`getTickInterval`),we=r(function(e){me=e},`setTodayMarker`),Te=r(function(){return me},`getTodayMarker`),Ee=r(function(e){L=e},`setDateFormat`),De=r(function(){K=!0},`enableInclusiveEndDates`),Oe=r(function(){return K},`endDatesAreInclusive`),ke=r(function(){ge=!0},`enableTopAxis`),Ae=r(function(){return ge},`topAxisEnabled`),je=r(function(e){W=e},`setDisplayMode`),Me=r(function(){return W},`getDisplayMode`),Ne=r(function(){return L},`getDateFormat`),Pe=r(function(e){R=e.toLowerCase().split(/[\s,]+/)},`setIncludes`),Fe=r(function(){return R},`getIncludes`),Ie=r(function(e){z=e.toLowerCase().split(/[\s,]+/)},`setExcludes`),Le=r(function(){return z},`getExcludes`),Re=r(function(){return B},`getLinks`),ze=r(function(e){U=e,V.push(e)},`addSection`),Be=r(function(){return V},`getSections`),Ve=r(function(){let e=rt(),t=0;for(;!e&&t<10;)e=rt(),t++;return H=Z,H},`getTasks`),He=r(function(e,t,n,r){let i=e.format(t.trim()),a=e.format(`YYYY-MM-DD`);return r.includes(i)||r.includes(a)?!1:n.includes(`weekends`)&&(e.isoWeekday()===de[q]||e.isoWeekday()===de[q]+1)||n.includes(e.format(`dddd`).toLowerCase())?!0:n.includes(i)||n.includes(a)},`isInvalidDate`),Ue=r(function(e){_e=e},`setWeekday`),We=r(function(){return _e},`getWeekday`),Ge=r(function(e){q=e},`setWeekend`),Ke=r(function(e,t,n,r){if(!n.length||e.manualEndTime)return;let i;i=e.startTime instanceof Date?(0,I.default)(e.startTime):(0,I.default)(e.startTime,t,!0),i=i.add(1,`d`);let a;a=e.endTime instanceof Date?(0,I.default)(e.endTime):(0,I.default)(e.endTime,t,!0);let[o,s]=qe(i,a,t,n,r);e.endTime=o.toDate(),e.renderEndTime=s},`checkTaskDates`),qe=r(function(e,t,n,r,i){let a=!1,o=null;for(;e<=t;)a||(o=t.toDate()),a=He(e,n,r,i),a&&(t=t.add(1,`d`)),e=e.add(1,`d`);return[t,o]},`fixTaskDates`),Je=r(function(e,t,n){if(n=n.trim(),(t.trim()===`x`||t.trim()===`X`)&&/^\d+$/.test(n))return new Date(Number(n));let r=/^after\s+(?<ids>[\d\w- ]+)/.exec(n);if(r!==null){let e=null;for(let t of r.groups.ids.split(` `)){let n=Q(t);n!==void 0&&(!e||n.endTime>e.endTime)&&(e=n)}if(e)return e.endTime;let t=new Date;return t.setHours(0,0,0,0),t}let a=(0,I.default)(n,t.trim(),!0);if(a.isValid())return a.toDate();{i.debug(`Invalid date:`+n),i.debug(`With date format:`+t.trim());let e=new Date(n);if(e===void 0||isNaN(e.getTime())||e.getFullYear()<-1e4||e.getFullYear()>1e4)throw Error(`Invalid date:`+n);return e}},`getStartDate`),Ye=r(function(e){let t=/^(\d+(?:\.\d+)?)([Mdhmswy]|ms)$/.exec(e.trim());return t===null?[NaN,`ms`]:[Number.parseFloat(t[1]),t[2]]},`parseDuration`),Xe=r(function(e,t,n,r=!1){n=n.trim();let i=/^until\s+(?<ids>[\d\w- ]+)/.exec(n);if(i!==null){let e=null;for(let t of i.groups.ids.split(` `)){let n=Q(t);n!==void 0&&(!e||n.startTime<e.startTime)&&(e=n)}if(e)return e.startTime;let t=new Date;return t.setHours(0,0,0,0),t}let a=(0,I.default)(n,t.trim(),!0);if(a.isValid())return r&&(a=a.add(1,`d`)),a.toDate();let o=(0,I.default)(e),[s,c]=Ye(n);if(!Number.isNaN(s)){let e=o.add(s,c);e.isValid()&&(o=e)}return o.toDate()},`getEndDate`),J=0,Y=r(function(e){return e===void 0?(J+=1,`task`+J):e},`parseId`),Ze=r(function(e,t){let n;n=t.substr(0,1)===`:`?t.substr(1,t.length):t;let r=n.split(`,`),i={};lt(r,i,he);for(let e=0;e<r.length;e++)r[e]=r[e].trim();let a=``;switch(r.length){case 1:i.id=Y(),i.startTime=e.endTime,a=r[0];break;case 2:i.id=Y(),i.startTime=Je(void 0,L,r[0]),a=r[1];break;case 3:i.id=Y(r[0]),i.startTime=Je(void 0,L,r[1]),a=r[2]}return a&&(i.endTime=Xe(i.startTime,L,a,K),i.manualEndTime=(0,I.default)(a,`YYYY-MM-DD`,!0).isValid(),Ke(i,L,z,R)),i},`compileData`),Qe=r(function(e,t){let n;n=t.substr(0,1)===`:`?t.substr(1,t.length):t;let r=n.split(`,`),i={};lt(r,i,he);for(let e=0;e<r.length;e++)r[e]=r[e].trim();switch(r.length){case 1:i.id=Y(),i.startTime={type:`prevTaskEnd`,id:e},i.endTime={data:r[0]};break;case 2:i.id=Y(),i.startTime={type:`getStartDate`,startData:r[0]},i.endTime={data:r[1]};break;case 3:i.id=Y(r[0]),i.startTime={type:`getStartDate`,startData:r[1]},i.endTime={data:r[2]}}return i},`parseData`),$e,X,Z=[],et={},tt=r(function(e,t){let n={section:U,type:U,processed:!1,manualEndTime:!1,renderEndTime:null,raw:{data:t},task:e,classes:[]},r=Qe(X,t);n.raw.startTime=r.startTime,n.raw.endTime=r.endTime,n.id=r.id,n.prevTaskId=X,n.active=r.active,n.done=r.done,n.crit=r.crit,n.milestone=r.milestone,n.vert=r.vert,n.order=ve,ve++;let i=Z.push(n);X=n.id,et[n.id]=i-1},`addTask`),Q=r(function(e){let t=et[e];return Z[t]},`findTaskById`),nt=r(function(e,t){let n={section:U,type:U,description:e,task:e,classes:[]},r=Ze($e,t);n.startTime=r.startTime,n.endTime=r.endTime,n.id=r.id,n.active=r.active,n.done=r.done,n.crit=r.crit,n.milestone=r.milestone,n.vert=r.vert,$e=n,H.push(n)},`addTaskOrg`),rt=r(function(){let e=r(function(e){let t=Z[e],n=``;switch(Z[e].raw.startTime.type){case`prevTaskEnd`:t.startTime=Q(t.prevTaskId).endTime;break;case`getStartDate`:n=Je(void 0,L,Z[e].raw.startTime.startData),n&&(Z[e].startTime=n)}return Z[e].startTime&&(Z[e].endTime=Xe(Z[e].startTime,L,Z[e].raw.endTime.data,K),Z[e].endTime&&(Z[e].processed=!0,Z[e].manualEndTime=(0,I.default)(Z[e].raw.endTime.data,`YYYY-MM-DD`,!0).isValid(),Ke(Z[e],L,z,R))),Z[e].processed},`compileTask`),t=!0;for(let[n,r]of Z.entries())e(n),t&&=r.processed;return t},`compileTasks`),it=r(function(e,t){let n=t;u().securityLevel!==`loose`&&(n=(0,F.sanitizeUrl)(t)),e.split(`,`).forEach(function(e){Q(e)!==void 0&&(st(e,()=>{window.open(n,`_self`)}),B.set(e,n))}),at(e,`clickable`)},`setLink`),at=r(function(e,t){e.split(`,`).forEach(function(e){let n=Q(e);n!==void 0&&n.classes.push(t)})},`setClass`),ot=r(function(e,t,n){if(u().securityLevel!==`loose`||t===void 0)return;let r=[];if(typeof n==`string`){r=n.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/);for(let e=0;e<r.length;e++){let t=r[e].trim();t.startsWith(`"`)&&t.endsWith(`"`)&&(t=t.substr(1,t.length-2)),r[e]=t}}r.length===0&&r.push(e),Q(e)!==void 0&&st(e,()=>{P.runFunc(t,...r)})},`setClickFun`),st=r(function(e,t){G.push(function(){let n=document.querySelector(`[id="${e}"]`);n!==null&&n.addEventListener(`click`,function(){t()})},function(){let n=document.querySelector(`[id="${e}-text"]`);n!==null&&n.addEventListener(`click`,function(){t()})})},`pushFun`),ct={getConfig:r(()=>u().gantt,`getConfig`),clear:ye,setDateFormat:Ee,getDateFormat:Ne,enableInclusiveEndDates:De,endDatesAreInclusive:Oe,enableTopAxis:ke,topAxisEnabled:Ae,setAxisFormat:be,getAxisFormat:xe,setTickInterval:Se,getTickInterval:Ce,setTodayMarker:we,getTodayMarker:Te,setAccTitle:a,getAccTitle:p,setDiagramTitle:s,getDiagramTitle:o,setDisplayMode:je,getDisplayMode:Me,setAccDescription:m,getAccDescription:c,addSection:ze,getSections:Be,getTasks:Ve,addTask:tt,findTaskById:Q,addTaskOrg:nt,setIncludes:Pe,getIncludes:Fe,setExcludes:Ie,getExcludes:Le,setClickEvent:r(function(e,t,n){e.split(`,`).forEach(function(e){ot(e,t,n)}),at(e,`clickable`)},`setClickEvent`),setLink:it,getLinks:Re,bindFunctions:r(function(e){G.forEach(function(t){t(e)})},`bindFunctions`),parseDuration:Ye,isInvalidDate:He,setWeekday:Ue,getWeekday:We,setWeekend:Ge};function lt(e,t,n){let r=!0;for(;r;)r=!1,n.forEach(function(n){let i=`^\\s*`+n+`\\s*$`,a=new RegExp(i);e[0].match(a)&&(t[n]=!0,e.shift(1),r=!0)})}r(lt,`getTaskTags`);var ut=r(function(){i.debug(`Something is calling, setConf, remove the call`)},`setConf`),dt={monday:x,tuesday:C,wednesday:j,thursday:S,friday:ee,saturday:D,sunday:ne},ft=r((e,t)=>{let n=[...e].map(()=>-1/0),r=[...e].sort((e,t)=>e.startTime-t.startTime||e.order-t.order),i=0;for(let e of r)for(let r=0;r<n.length;r++)if(e.startTime>=n[r]){n[r]=e.endTime,e.order=r+t,r>i&&(i=r);break}return i},`getMaxIntersections`),$,pt={parser:ue,db:ct,renderer:{setConf:ut,draw:r(function(e,t,a,o){let s=u().gantt,c=u().securityLevel,l;c===`sandbox`&&(l=n(`#i`+t));let p=n(c===`sandbox`?l.nodes()[0].contentDocument.body:`body`),m=c===`sandbox`?l.nodes()[0].contentDocument:document,x=m.getElementById(t);$=x.parentElement.offsetWidth,$===void 0&&($=1200),s.useWidth!==void 0&&($=s.useWidth);let S=o.db.getTasks(),C=[];for(let e of S)C.push(e.type);C=se(C);let D={},k=2*s.topPadding;if(o.db.getDisplayMode()===`compact`||s.displayMode===`compact`){let e={};for(let t of S)e[t.section]===void 0?e[t.section]=[t]:e[t.section].push(t);let t=0;for(let n of Object.keys(e)){let r=ft(e[n],t)+1;t+=r,k+=r*(s.barHeight+s.barGap),D[n]=r}}else{k+=S.length*(s.barHeight+s.barGap);for(let e of C)D[e]=S.filter(t=>t.type===e).length}x.setAttribute(`viewBox`,`0 0 `+$+` `+k);let j=p.select(`[id="${t}"]`),M=E().domain([_(S,function(e){return e.startTime}),g(S,function(e){return e.endTime})]).rangeRound([0,$-s.leftPadding-s.rightPadding]);function ee(e,t){let n=e.startTime,r=t.startTime,i=0;return n>r?i=1:n<r&&(i=-1),i}r(ee,`taskCompare`),S.sort(ee),te(S,$,k),d(j,k,$,s.useMaxWidth),j.append(`text`).text(o.db.getDiagramTitle()).attr(`x`,$/2).attr(`y`,s.titleTopMargin).attr(`class`,`titleText`);function te(e,t,n){let r=s.barHeight,i=r+s.barGap,a=s.topPadding,c=s.leftPadding,l=h().domain([0,C.length]).range([`#00B9FA`,`#F95002`]).interpolate(ae);N(i,a,c,t,n,e,o.db.getExcludes(),o.db.getIncludes()),P(c,a,t,n),ne(e,i,a,c,r,l,t,n),F(i,a,c,r,l),oe(c,a,t,n)}r(te,`makeGantt`);function ne(e,r,i,a,c,l,d){e.sort((e,t)=>e.vert===t.vert?0:e.vert?1:-1);let f=[...new Set(e.map(e=>e.order))].map(t=>e.find(e=>e.order===t));j.append(`g`).selectAll(`rect`).data(f).enter().append(`rect`).attr(`x`,0).attr(`y`,function(e,t){return t=e.order,t*r+i-2}).attr(`width`,function(){return d-s.rightPadding/2}).attr(`height`,r).attr(`class`,function(e){for(let[t,n]of C.entries())if(e.type===n)return`section section`+t%s.numberSectionStyles;return`section section0`}).enter();let p=j.append(`g`).selectAll(`rect`).data(e).enter(),m=o.db.getLinks();if(p.append(`rect`).attr(`id`,function(e){return e.id}).attr(`rx`,3).attr(`ry`,3).attr(`x`,function(e){return e.milestone?M(e.startTime)+a+.5*(M(e.endTime)-M(e.startTime))-.5*c:M(e.startTime)+a}).attr(`y`,function(e,t){return t=e.order,e.vert?s.gridLineStartPadding:t*r+i}).attr(`width`,function(e){return e.milestone?c:e.vert?.08*c:M(e.renderEndTime||e.endTime)-M(e.startTime)}).attr(`height`,function(e){return e.vert?S.length*(s.barHeight+s.barGap)+s.barHeight*2:c}).attr(`transform-origin`,function(e,t){return t=e.order,(M(e.startTime)+a+.5*(M(e.endTime)-M(e.startTime))).toString()+`px `+(t*r+i+.5*c).toString()+`px`}).attr(`class`,function(e){let t=``;e.classes.length>0&&(t=e.classes.join(` `));let n=0;for(let[t,r]of C.entries())e.type===r&&(n=t%s.numberSectionStyles);let r=``;return e.active?e.crit?r+=` activeCrit`:r=` active`:e.done?r=e.crit?` doneCrit`:` done`:e.crit&&(r+=` crit`),r.length===0&&(r=` task`),e.milestone&&(r=` milestone `+r),e.vert&&(r=` vert `+r),r+=n,r+=` `+t,`task`+r}),p.append(`text`).attr(`id`,function(e){return e.id+`-text`}).text(function(e){return e.task}).attr(`font-size`,s.fontSize).attr(`x`,function(e){let t=M(e.startTime),n=M(e.renderEndTime||e.endTime);if(e.milestone&&(t+=.5*(M(e.endTime)-M(e.startTime))-.5*c,n=t+c),e.vert)return M(e.startTime)+a;let r=this.getBBox().width;return r>n-t?n+r+1.5*s.leftPadding>d?t+a-5:n+a+5:(n-t)/2+t+a}).attr(`y`,function(e,t){return e.vert?s.gridLineStartPadding+S.length*(s.barHeight+s.barGap)+60:(t=e.order,t*r+s.barHeight/2+(s.fontSize/2-2)+i)}).attr(`text-height`,c).attr(`class`,function(e){let t=M(e.startTime),n=M(e.endTime);e.milestone&&(n=t+c);let r=this.getBBox().width,i=``;e.classes.length>0&&(i=e.classes.join(` `));let a=0;for(let[t,n]of C.entries())e.type===n&&(a=t%s.numberSectionStyles);let o=``;return e.active&&(o=e.crit?`activeCritText`+a:`activeText`+a),e.done?o=e.crit?o+` doneCritText`+a:o+` doneText`+a:e.crit&&(o=o+` critText`+a),e.milestone&&(o+=` milestoneText`),e.vert&&(o+=` vertText`),r>n-t?n+r+1.5*s.leftPadding>d?i+` taskTextOutsideLeft taskTextOutside`+a+` `+o:i+` taskTextOutsideRight taskTextOutside`+a+` `+o+` width-`+r:i+` taskText taskText`+a+` `+o+` width-`+r}),u().securityLevel===`sandbox`){let e;e=n(`#i`+t);let r=e.nodes()[0].contentDocument;p.filter(function(e){return m.has(e.id)}).each(function(e){var t=r.querySelector(`#`+e.id),n=r.querySelector(`#`+e.id+`-text`);let i=t.parentNode;var a=r.createElement(`a`);a.setAttribute(`xlink:href`,m.get(e.id)),a.setAttribute(`target`,`_top`),i.appendChild(a),a.appendChild(t),a.appendChild(n)})}}r(ne,`drawRects`);function N(e,t,n,r,a,c,l,u){if(l.length===0&&u.length===0)return;let d,f;for(let{startTime:e,endTime:t}of c)(d===void 0||e<d)&&(d=e),(f===void 0||t>f)&&(f=t);if(!d||!f)return;if((0,I.default)(f).diff((0,I.default)(d),`year`)>5){i.warn(`The difference between the min and max time is more than 5 years. This will cause performance issues. Skipping drawing exclude days.`);return}let p=o.db.getDateFormat(),m=[],h=null,g=(0,I.default)(d);for(;g.valueOf()<=f;)o.db.isInvalidDate(g,p,l,u)?h?h.end=g:h={start:g,end:g}:h&&=(m.push(h),null),g=g.add(1,`d`);j.append(`g`).selectAll(`rect`).data(m).enter().append(`rect`).attr(`id`,e=>`exclude-`+e.start.format(`YYYY-MM-DD`)).attr(`x`,e=>M(e.start.startOf(`day`))+n).attr(`y`,s.gridLineStartPadding).attr(`width`,e=>M(e.end.endOf(`day`))-M(e.start.startOf(`day`))).attr(`height`,a-t-s.gridLineStartPadding).attr(`transform-origin`,function(t,r){return(M(t.start)+n+.5*(M(t.end)-M(t.start))).toString()+`px `+(r*e+.5*a).toString()+`px`}).attr(`class`,`exclude-range`)}r(N,`drawExcludeDays`);function P(e,t,n,r){let i=o.db.getDateFormat(),a=o.db.getAxisFormat(),c;c=a||(i===`D`?`%d`:s.axisFormat??`%Y-%m-%d`);let l=b(M).tickSize(-r+t+s.gridLineStartPadding).tickFormat(y(c)),u=/^([1-9]\d*)(millisecond|second|minute|hour|day|week|month)$/.exec(o.db.getTickInterval()||s.tickInterval);if(u!==null){let e=u[1],t=u[2],n=o.db.getWeekday()||s.weekday;switch(t){case`millisecond`:l.ticks(re.every(e));break;case`second`:l.ticks(v.every(e));break;case`minute`:l.ticks(w.every(e));break;case`hour`:l.ticks(T.every(e));break;case`day`:l.ticks(O.every(e));break;case`week`:l.ticks(dt[n].every(e));break;case`month`:l.ticks(A.every(e))}}if(j.append(`g`).attr(`class`,`grid`).attr(`transform`,`translate(`+e+`, `+(r-50)+`)`).call(l).selectAll(`text`).style(`text-anchor`,`middle`).attr(`fill`,`#000`).attr(`stroke`,`none`).attr(`font-size`,10).attr(`dy`,`1em`),o.db.topAxisEnabled()||s.topAxis){let n=ie(M).tickSize(-r+t+s.gridLineStartPadding).tickFormat(y(c));if(u!==null){let e=u[1],t=u[2],r=o.db.getWeekday()||s.weekday;switch(t){case`millisecond`:n.ticks(re.every(e));break;case`second`:n.ticks(v.every(e));break;case`minute`:n.ticks(w.every(e));break;case`hour`:n.ticks(T.every(e));break;case`day`:n.ticks(O.every(e));break;case`week`:n.ticks(dt[r].every(e));break;case`month`:n.ticks(A.every(e))}}j.append(`g`).attr(`class`,`grid`).attr(`transform`,`translate(`+e+`, `+t+`)`).call(n).selectAll(`text`).style(`text-anchor`,`middle`).attr(`fill`,`#000`).attr(`stroke`,`none`).attr(`font-size`,10)}}r(P,`makeGrid`);function F(e,t){let n=0,r=Object.keys(D).map(e=>[e,D[e]]);j.append(`g`).selectAll(`text`).data(r).enter().append(function(e){let t=e[0].split(f.lineBreakRegex),n=-(t.length-1)/2,r=m.createElementNS(`http://www.w3.org/2000/svg`,`text`);r.setAttribute(`dy`,n+`em`);for(let[e,n]of t.entries()){let t=m.createElementNS(`http://www.w3.org/2000/svg`,`tspan`);t.setAttribute(`alignment-baseline`,`central`),t.setAttribute(`x`,`10`),e>0&&t.setAttribute(`dy`,`1em`),t.textContent=n,r.appendChild(t)}return r}).attr(`x`,10).attr(`y`,function(i,a){if(a>0)for(let o=0;o<a;o++)return n+=r[a-1][1],i[1]*e/2+n*e+t;else return i[1]*e/2+t}).attr(`font-size`,s.sectionFontSize).attr(`class`,function(e){for(let[t,n]of C.entries())if(e[0]===n)return`sectionTitle sectionTitle`+t%s.numberSectionStyles;return`sectionTitle`})}r(F,`vertLabels`);function oe(e,t,n,r){let i=o.db.getTodayMarker();if(i===`off`)return;let a=j.append(`g`).attr(`class`,`today`),c=new Date,l=a.append(`line`);l.attr(`x1`,M(c)+e).attr(`x2`,M(c)+e).attr(`y1`,s.titleTopMargin).attr(`y2`,r-s.titleTopMargin).attr(`class`,`today`),i!==``&&l.attr(`style`,i.replace(/,/g,`;`))}r(oe,`drawToday`);function se(e){let t={},n=[];for(let r=0,i=e.length;r<i;++r)Object.prototype.hasOwnProperty.call(t,e[r])||(t[e[r]]=!0,n.push(e[r]));return n}r(se,`checkUnique`)},`draw`)},styles:r(e=>`
  .mermaid-main-font {
        font-family: ${e.fontFamily};
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
    font-family: ${e.fontFamily};
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
    font-family: ${e.fontFamily};
  }

  .taskTextOutsideRight {
    fill: ${e.taskTextDarkColor};
    text-anchor: start;
    font-family: ${e.fontFamily};
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

  .vert {
    stroke: ${e.vertLineColor};
  }

  .vertText {
    font-size: 15px;
    text-anchor: middle;
    fill: ${e.vertLineColor} !important;
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
    font-family: ${e.fontFamily};
  }
`,`getStyles`)};export{pt as diagram};