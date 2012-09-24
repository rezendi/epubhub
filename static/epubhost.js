$(document).ready(function() {
  if (epub_share && epub_share=="true") {
    $("body").prepend(getHeader());
    $("body").mouseup(function() {
	  addSelectedHTML();
	});
    $("p").hover(function() {
	  if (htmlSelected())
		return;
      $(".eph_floater").remove();
      var included = added.indexOf( $("p").index($(this)) );
      var span = "";
      if (included < 0) {
        $(this).click(function() { eph_addPara($(this)); });
        span = "<span class=\'eph_floater\' style=\'float:right;color:blue;\'>+</span>"
        $(span).insertBefore($(this));
      }
      else {
        $(this).click(function() { eph_subtractPara($(this)); });
		$("#eph_action").html(getShareLink());
      }
    });
  }
  else
    $("#header").append(getContentsLink("top"));
});

var added = new Array();

var eph_addPara = function(para) {
  if (htmlSelected()) {
	addSelectedHTML();
	return;
  }
  var toAdd = $("p").index(para);
  for (var i=0; i<added.length; i++) {
    if (added[i]==toAdd)
      return;
  }
  added.push($("p").index(para))
  para.css("background-color","gainsboro");
  $("#eph_action").html(getShareLink());
  para.click(function() { eph_subtractPara($(this)); });
}

var eph_subtractPara = function(para) {
  var toRemove = $("p").index(para);
  for (var i=0; i<added.length; i++) {
    if (added[i]==toRemove)
      added.splice(i,1);
  }
  para.css("background-color","");
  $("#eph_action").html('Click on or select text to share a quote');
  para.click(function() { eph_addPara($(this)); });
  if (htmlSelected())
	addSelectedHTML();
}

var eph_share = function() {
  $(".eph_floater").text("...");
  var html = getSelectedHTML();
  if (html.length==0) {
	added = added.sort();
	$("p").each(function(index) {
	  if (added.indexOf(index)>=0)
	  html+="<p>"+$(this).html()+"</p>\n";
	});
  }
  $("#eph_action").html("Sharing...");
  $.ajax({type: 'POST',
		  url: '/share',
		  dataType: 'json',
		  data: {'html' : html, 'epub' : epub_id, 'file' : epub_internal},
		  success: onShareSuccess,
		  error: onShareError});
}

var onShareSuccess = function(results) {
  $(".eph_floater").remove();
  $("p").css("background-color","");
  added = new Array();
  $("#eph_action").html("Shared to <a target='_blank' href='"+results["url"]+"'>"+results["url"]+"</a>");
}

var onShareError = function(error) {
  alert("Error: "+error);
}

var getHeader = function(name) {
  var html = "<div id='eph_header' style='position:fixed;'>";
  html+= "<a style='margin-left:15px; float:left;' href='/view/"+epub_id+"/"+epub_prev+"'>Prev</a>";
  html+= "<a href='/' style='margin-right:20px;'>Home</a> <a href='/book/"+epub_id+"'>"+epub_title+", Section "+epub_chapter+" of "+epub_total+" </a>";
  html+= "<span id='eph_action' style='margin-left:50px;color:#999;'>Click on or select text to share a quote</span>";
  html+= "<a style='float:right;' href='/view/"+epub_id+"/"+epub_next+"'>Next</a>";
  html+= "</div>";
  html+= "<div id='eph_spacer'>&nbsp;</div>";
  return html;
}

var getContentsLink = function() {
  html = "<a style='float:right;font-weight:bold;' href='/book/"+epub_id+"'>"+epub_title+"</a>";
  return html;
}

var getShareLink = function() {
  return "<a href=\'#\' style=\'text-decoration:none;\' onclick=\'eph_share();\'>Share Selected Text</a>"
}

var htmlSelected = function() {
  return getSelectedHTML().length > 0;
}

var addSelectedHTML = function() {
  if (!htmlSelected() || $("#eph_action").html().indexOf(getSelectedHTML())>=0)
	return;
  $("p").css("background-color","");
  added = new Array();
  $("#eph_action").html(getShareLink());
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
