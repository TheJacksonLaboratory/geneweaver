// Simple SVG pan/zoom script
// Written October 12-13 2010
// By Jeremy Jay

// create java-style namespace
if ( typeof(com) == "undefined" ){ com = {}; }
if ( typeof(com.pbnjay) == "undefined" ){ com.pbnjay = {}; }

com.pbnjay.PanZoomSVG = (function(){
	var svg=document.documentElement;
	var b=svg.viewBox.baseVal;
	var zoom_left=b.x,zoom_width=b.width,zoom_top=b.y,zoom_height=b.height,zoom_start=0;
	var mouse_x=0, mouse_y=0, mouse_down=0;
	var start_x, start_y;
	var rect = null;
	var _ns = new Object();

	_ns.init = function() {
		window.addEventListener('mousedown', function(e){ com.pbnjay.PanZoomSVG.onmousedown(e); }, false);
		window.addEventListener('mouseup', function(e){ com.pbnjay.PanZoomSVG.onmouseup(e); }, false);
		svg.addEventListener('mouseout', function(e){ com.pbnjay.PanZoomSVG.onmouseup(e); }, false);
		window.addEventListener('mousemove', function(e){ com.pbnjay.PanZoomSVG.onmousemove(e); }, false);
		// WebKit (chrome, safari, etc)
		window.addEventListener('mousewheel', function(e){ com.pbnjay.PanZoomSVG.onwheel(e); }, false);
		// gecko (firefox et al)
		window.addEventListener('DOMMouseScroll', function(e){ com.pbnjay.PanZoomSVG.onwheel(e); }, false);
	}
	_ns.zoomBox = function (cx,cy,scale) {
		var nw=b.width*scale, nh=b.height*scale;
		var nx=cx-(nw/2);
		var ny=cy-(nh/2);

		_ns.zoomBoxTo(nx,ny,nw,nh);
	}
	_ns.zoomBoxTo = function (nx,ny,nw,nh) {
		zoom_left=nx;
		zoom_top=ny;
		zoom_width=nw;
		zoom_height=nh;
		zoom_start=new Date().getTime();

		_ns._zoomer();
	}
	_ns._zoomer = function () {
		var now=new Date().getTime();
		var zoom_frames=(now-zoom_start)/50;
		if( zoom_frames<1 ) zoom_frames=1;
		if( zoom_frames>10 ) zoom_frames=10;
		var alpha=zoom_frames/10;

		b.x=(zoom_left*alpha)+(1.0-alpha)*b.x;
		b.y=(zoom_top*alpha)+(1.0-alpha)*b.y;
		b.width=(zoom_width*alpha)+(1.0-alpha)*b.width;
		b.height=(zoom_height*alpha)+(1.0-alpha)*b.height;

		if( zoom_frames<10 ) { 
			setTimeout("com.pbnjay.PanZoomSVG._zoomer()", 50);
		} else {
			b.x=zoom_left;
			b.y=zoom_top;
			b.width=zoom_width;
			b.height=zoom_height;
		}
	}
	_ns.panBox = function (dx,dy) {
		b.x+=dx;
		b.y+=dy;
	}
	_ns.onmousemove = function (evt) {
		if( mouse_down==1 ) {
			var mx=start_x;
			var my=start_y;
			_ns.mapmouse(evt.clientX, evt.clientY);
			var dx=mx-mouse_x;
			var dy=my-mouse_y;

			_ns.panBox(dx, dy);
			evt.preventDefault();
		} else if( mouse_down==2 ) {
			_ns.mapmouse(evt.clientX, evt.clientY);

			// i would like to draw a pretty zoom-rect...
		  if( rect==null ) rect=document.getElementById('zoomhi');
			if( rect!=null ) {
				x=mouse_x<start_x?mouse_x:start_x;
				y=mouse_y<start_y?mouse_y:start_y;
				w=mouse_x-start_x;
				h=mouse_y-start_y;
				if( w<0 ) w=-w;
				if( h<0 ) h=-h;
				rect.setAttribute("x", x);
				rect.setAttribute("y", y);
				rect.setAttribute("width", w);
				rect.setAttribute("height", h);
				rect.setAttribute("fill", "blue");
				rect.setAttribute("fill-opacity", "0.1");
			}

			evt.preventDefault();
		}
	}
	_ns.onmousedown = function (evt) {
		_ns.mapmouse(evt.clientX, evt.clientY);
		mouse_down=1;
		start_x=mouse_x;
		start_y=mouse_y;
		if( evt.metaKey && svg.getScreenCTM ) {
			mouse_down=2;
		}
		evt.preventDefault();
	}
	_ns.onmouseup = function (evt) {
		_ns.mapmouse(evt.clientX, evt.clientY);
		if( mouse_down==2 && mouse_x!=start_x && mouse_y!=start_y ) {
			x=mouse_x<start_x?mouse_x:start_x;
			y=mouse_y<start_y?mouse_y:start_y;
			w=mouse_x-start_x;
			h=mouse_y-start_y;
			if( w<0 ) w=-w;
			if( h<0 ) h=-h;
			_ns.zoomBoxTo(x,y,w,h);
			if( rect!=null )
				rect.setAttribute('fill-opacity', '0.0');
		}
		mouse_down=0;
		if( evt.detail>1 && (evt.detail%2)==0 ) {
			if( evt.shiftKey ) {
				_ns.zoomBox(mouse_x,mouse_y,1.6666);
			} else {
				_ns.zoomBox(mouse_x,mouse_y,0.6);
			}
		}
		evt.preventDefault();
	}
	_ns.onwheel = function (evt) {
		var deltaX=0, deltaY=0;
    
    // Webkit
		if ( evt.wheelDelta ) {
			deltaY = evt.wheelDelta/250;
			if ( evt.wheelDeltaY !== undefined ) { deltaY = -evt.wheelDeltaY/250; }
			if ( evt.wheelDeltaX !== undefined ) { deltaX = -evt.wheelDeltaX/250; }
		} else { // Gecko
			if ( evt.axis !== undefined && evt.axis === evt.HORIZONTAL_AXIS ) {
        deltaX = evt.detail;
			} else {
        deltaY = evt.detail;
 			}
    }
    
		_ns.panBox(deltaX,deltaY);
		evt.preventDefault();
	}
	_ns.mapmouse = function (mmx,mmy) {
		// only good browsers can do this...
		if( !svg.getScreenCTM ) {
			mouse_x=mx;
			mouse_y=my;
			return;
		}
		var matrix = svg.getScreenCTM().inverse();
		var pt = svg.createSVGPoint();
		pt.x=mmx;
		pt.y=mmy;
		var pt = pt.matrixTransform( matrix );
		mouse_x=pt.x;
		mouse_y=pt.y;
	}

	return _ns;
})();

// auto-load listeners
(function(){
 com.pbnjay.PanZoomSVG.init();
})();

