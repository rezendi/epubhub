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
    $("#header").append(getLink("top"));

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
  if (name=="top")
    html = "<div id='eph_header' style='margin-top:8px;margin-left:2px;'>";
  else
    html = "<div style='background-color:gainsboro;margin-bottom:8px;'>";
  html+= "<a style='float:left; href='/view/"+epub_file+"/"+epub_prev+"'>Prev</a>";
  if (name=="top") {
    html+= "<a href='/' style='margin-right:20px;'>Home</a> <a href='/contents?key="+epub_file+"'>"+epub_title+", Chapter "+epub_chapter+" of "+epub_total+" </a>";
	html+= "<span style='margin-left:50px;color:#999;'>Click on or select text to share a quote</span>";
  }
  else
	html+= "&nbsp;"
  html+= "<a style='float:right;' href='/view/"+epub_file+"/"+epub_next+"'>Next</a>";
  html+= "</div>";
  return html;
}

var getLink = function() {
  html = "<a style='float:right;font-weight:bold;' href='/contents?key="+epub_file+"'>"+epub_title+"</a>";
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
