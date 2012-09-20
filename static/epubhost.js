$(document).ready(function() {
  if (epub_share && epub_share=="true") {
    $("body").prepend(getBar("top"));
    $("body").append(getBar("bottom"));
    $("p").hover(function() {
      $(".eph_floater").remove();
      var included = added.indexOf( $("p").index($(this)) );
      var span = "";
      if (included < 0) {
        span = "<span class=\'eph_floater\' style=\'float:right;color:blue;\'>+</span>"
        $(this).click(function() { eph_addPara($(this)); });
      }
      else {
        span = "<span class=\'eph_floater\' style=\'float:right;color:blue;\'><a href=\'#\' style=\'text-decoration:none;\' onclick=\'eph_share();\'>SHARE THIS QUOTE</a></span>"
        $(this).click(function() { eph_subtractPara($(this)); });
      }
      $(span).insertBefore($(this));
    });
  }
  else
    $("body").prepend(getLink("top"));

});

var added = new Array();

var eph_addPara = function(para) {
  var toAdd = $("p").index(para);
  for (var i=0; i<added.length; i++) {
    if (added[i]==toAdd)
      return;
  }
  added.push($("p").index(para))
  para.css("background-color","gainsboro");
  $(".eph_floater").html('<a href=\'#\' style=\'text-decoration:none;\' onclick=\'eph_share();\'>SHARE THIS QUOTE</a>');
  para.click(function() { eph_subtractPara($(this)); });
}

var eph_subtractPara = function(para) {
  var toRemove = $("p").index(para);
  for (var i=0; i<added.length; i++) {
    if (added[i]==toRemove)
      added.splice(i,1);
  }
  para.css("background-color","");
  $(".eph_floater").text("+");
  para.click(function() { eph_addPara($(this)); });
}

var eph_share = function() {
  $(".eph_floater").text("...");
  added = added.sort();
  html = "";
  $("p").each(function(index) {
    if (added.indexOf(index)>=0)
    html+="<p>"+$(this).html()+"</p>\n";
  });
  $.ajax({type: 'POST',
		  url: '/share',
		  dataType: 'json',
		  data: {'html' : html, 'epub' : epub_file, 'file' : epub_internal},
		  success: onShareSuccess,
		  error: onShareError});
}

var onShareSuccess = function(results) {
  $(".eph_floater").remove();
  $("p").css("background-color","");
  added = new Array();
  alert("Shared to "+results["url"]);
}

var onShareError = function(error) {
  alert("Error: "+error);
}

var getBar = function(name) {
  html = "<div style='width:100%;text-align:center;background-color:lightgray;' class='epubhost-bar' id='"+name+"-epubhost-bar'>";
  html+= "<span style='float:left;'><a href='/view/"+epub_file+"/"+epub_prev+"'>Prev</a></span>";
  html+= "<span><a href='/'>ePubHost</a> <a href='/contents?key="+epub_file+"'>"+epub_title+", Chapter "+epub_chapter+" of "+epub_total+" </a></span>";
  html+= "<span style='float:right;'><a href='/view/"+epub_file+"/"+epub_next+"'>Next</a></span>";
  html+= "</div>";
  return html;
}

var getLink = function() {
  html = "<div style='width:100%;text-align:center;background-color:lightgray;' class='epubhost-bar' id='"+name+"-epubhost-bar'>";
  html+= "<span style='float:left;'><a href='/'>ePubHost</a></span>";
  html+= '&nbsp;'
  html+= "<span style='float:right;'><a href='/contents?key="+epub_file+"'>"+epub_title+"</a></span>";
  html+= "</div>";
  return html;
}

var getSelectedHTML = function() {
    var html = "";
    if (typeof window.getSelection != "undefined") {
        var sel = window.getSelection();
        if (sel.rangeCount) {
            var container = document.createElement("div");
            for (var i = 0, len = sel.rangeCount; i < len; ++i) {
                container.appendChild(sel.getRangeAt(i).cloneContents());
            }
            html = container.innerHTML;
        }
    } else if (typeof document.selection != "undefined") {
        if (document.selection.type == "Text") {
            html = document.selection.createRange().htmlText;
        }
    }
    return html;
}
