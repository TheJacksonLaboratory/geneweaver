function isCanvasSupported(){
    var elem=document.createElement('canvas');
    return !!(elem.getContext && elem.getContext('2d'));
}
function getItemStyles(item){
    //this appends all the relavent styles to the copy of the graph
    var styleDefs="";
    for(var i=0;i<document.styleSheets.length;i++){
        var rules=document.styleSheets[i].cssRules;
        if(rules!=null){
            for(var j=0;j<rules.length;j++){
                var rule=rules[j];
                if(rule.style){
                    var selectorText=rule.selectorText;
                    var elems=item.querySelectorAll(selectorText);
                    if(elems.length){
                        styleDefs+=selectorText+" { "+rule.style.cssText+" }\n";
                    }
                }
            }
        }
    }
    return styleDefs;
}

//item: the svg to download
//styleTweak: a function that edits the existing css that applies to the svg,
//  takes one argument
//      i.e.
//  styleTweak(cssString){
//      cssString.replace("blue","red");
//      return cssString;
//  }
//
//asPng: a bool specifying if it should be a png or an svg
function download(item,styleTweak,asPng) {
    //alert("take a screenshot you lazy good-for-nothing");

    var style=getItemStyles(item);
    if(styleTweak){
        style=styleTweak(style);
    }

    var itemCopy=item.cloneNode(true);
    var fileName="chart";
    var styleDOM=document.createElement('style');
    styleDOM.setAttribute('type','text/css');
    styleDOM.innerHTML=style;
    itemCopy.insertBefore(styleDOM,itemCopy.firstChild);

    //serialize it to an svg
    var xml= new XMLSerializer().serializeToString(itemCopy);
    var data= "data:image/svg+xml;base64,"+btoa(xml);
    var extension="svg";


    if(asPng){
        if(!isCanvasSupported()){
            alert("your browser doesn't support html canvas\n"+
                  "    the graph will download as an svg");
        }else{
            //use the new html5 canvas stuff to convert svg data to png
            var img=new Image();
            img.src=data;
            var canvas = document.createElement('canvas');
            canvas.width=itemCopy.getAttribute('width');
            canvas.height=itemCopy.getAttribute('height');
            var context = canvas.getContext("2d").drawImage(img,0,0);
            data= canvas.toDataURL("image/png");
            extension="png";
        }
    }


    var a=document.createElement("a");
    a.setAttribute('href',data);
    a.setAttribute('download',fileName+"."+extension);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);


}