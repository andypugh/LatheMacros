#!/usr/bin/env python3
# vim: sts=4 sw=4 et
#    This is a component of EMC
#    savestate.py copyright 2013 Andy Pugh
#    based on code from 
#    probe.py Copyright 2010 Michael Haberler
#
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA''''''

import os,sys
from gladevcp.persistence import IniFile,widget_defaults,set_debug,select_widgets
import hal
import hal_glib
import glib
import linuxcnc
import cairo
import signal
import re
import gi
gi.require_version('Rsvg', '2.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Pango
from gi.repository import Rsvg
from gi.repository import GdkPixbuf
debug = 0
notouch = 0
norun = 0
svgfile = os.path.join(os.path.dirname(__file__), "LatheMacro.svg")

class HandlerClass:
    active = False
    tab_num = 0
    
    def focus_in(self, obj, event, data=None):
        self.active = True
        self.update_tabs(self.nb)
        
    def focus_out(self, obj, event, data=None):
        self.active = False

    def update_tabs(self,nb,data=None):
        for tab_num in range(nb.get_n_pages()):
            tab = nb.get_nth_page(tab_num)
            im = [c for c in tab.get_children() if isinstance(c, Gtk.Image)][0]
            #unlock resizing for the image FIXME - not actually working
            #im.set_size_request(1,1)  
            #im.set_halign(Gtk.Align.FILL)
            #im.set_valign(Gtk.Align.FILL)
            alloc = tab.get_allocation()
            w, h = alloc.width, alloc.height
            pixbuf = self.svg.get_pixbuf_sub(f'#layer{tab_num}').scale_simple(w * 0.98, h * 0.98, GdkPixbuf.InterpType.BILINEAR)
            im.set_from_pixbuf(pixbuf)
            for c in im.get_parent().get_children():
                if c.get_has_tooltip():
                    m = re.findall(r'<!--(\d+),(\d+)-->', c.get_tooltip_markup())
                    if len(m) > 0:
                        x1 = int(m[0][0]); y1 = int(m[0][1])
                        c.set_margin_left(max(0, w * x1/1500))
                        c.set_margin_top(max(0, h * y1/1000))
            
    def switch_page(self, nb, tab, tab_num, data=None):
        self.update_tabs(nb)
        
    def on_destroy(self,obj,data=None):
        self.ini.save_state(self)

    def on_restore_defaults(self,button,data=None):
        '''
        example callback for 'Reset to defaults' button
        currently unused
        '''
        self.ini.create_default_ini()
        self.ini.restore_state(self)

    def __init__(self, halcomp,builder,useropts):
        self.halcomp = halcomp
        self.builder = builder
        self.ini_filename = 'savestate.sav'
        self.defaults = {  IniFile.vars: dict(),
                           IniFile.widgets : widget_defaults(select_widgets(self.builder.get_objects(),
                           hal_only=False,output_only = True))
                        }
        self.ini = IniFile(self.ini_filename,self.defaults,self.builder)
        self.ini.restore_state(self)

        # A pin to use a physical switch to start the cycle
        self.cycle_start = hal_glib.GPin(halcomp.newpin('cycle-start', hal.HAL_BIT, hal.HAL_IN))
        self.cycle_start.connect('value-changed', self.cycle_pin)
        
        self.cmd = linuxcnc.command()

        # This connects the events to re-draw and scale the SVG frames
        self.nb = self.builder.get_object('Cycles')
        self.nb.connect("switch-page", self.switch_page)
        self.nb.connect("destroy", Gtk.main_quit)
        self.nb.add_events(Gdk.EventMask.STRUCTURE_MASK)
        self.svg = Rsvg.Handle().new_from_file(svgfile)
        self.active = False
        #self.update_tabs(self.nb)
        
        e = self.builder.get_object('macrobox')
        e.set_can_focus(True)
        e.add_events(Gdk.EventMask.FOCUS_CHANGE_MASK)
        e.connect_after("focus-in-event", self.focus_in)
        e.connect_after("focus-out-event", self.focus_out)
        
        # handle Useropts
        if norun:
            for tab_num in range(self.nb.get_n_pages()):
                name = Gtk.Buildable.get_name(self.nb.get_nth_page(tab_num))
                self.builder.get_object(f'{name}.action').set_visible(False)

    def show_keyb(self, obj, data=None):
        if notouch: return False
        self.active_ctrl = obj
        self.keyb = self.builder.get_object('keyboard')
        self.entry = self.builder.get_object('entry1')
        self.entry.modify_font(Pango.FontDescription("courier 42"))
        self.entry.set_text("")
        resp = self.keyb.run()
        return True

    def keyb_prev_click(self, obj, data=None):
        self.entry.set_text(self.active_ctrl.get_text())

    def keyb_number_click(self, obj, data=None):
        data = self.entry.get_text()
        data = data + obj.get_label()
        if any( x in data for x in [ '/2', '/4', '/8', '/16', '/32', '/64', '/128']):
            v = [0] + [float(x) for x in data.replace('/','.').split('.')]
            data = f'{v[-3] + v[-2]/v[-1]:6.7}'
        self.entry.set_text(data)

    def keyb_pm_click(self, obj, data=None):
        data = self.entry.get_text()
        if not data:
            data = "-"
        elif data[0] == '-':
            data = data[1:]
        else:
            data = '-' + data
        self.entry.set_text(data) 

    def keyb_convert_click(self, obj, data=None):
        v = float(self.entry.get_text())
        op = obj.get_label()
        if op == 'in->mm':
            self.entry.set_text(f'{v * 25.4:6.4}')
        elif op == 'mm->in':
            self.entry.set_text(f'{v / 25.4:6.4}')
        elif op == 'tpi->pitch':
            self.entry.set_text(f'{25.4 / v:6.4}')
        elif op == 'pitch->tpi':
            self.entry.set_text(f'{25.4 / v:6.4}')

    def keyb_del_click(self, obj, data=None):
        data = self.entry.get_text()
        data = data[:-1]
        self.entry.set_text(data)

    def keyb_clear_click(self, obj, data=None):
        self.entry.set_text('')

    def keyb_cancel_click(self, obj, data=None):
        self.keyb.hide()

    def keyb_ok_click(self, obj, data=None):
        if self.entry.get_text() != '':
            self.active_ctrl.set_value(float(self.entry.get_text()))
        self.keyb.hide()

    def set_alpha(self, obj, data = None):
        cr = obj.get_property('window').cairo_create()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.0)

    def cycle_pin(self, pin, data = None):
        if pin.get() == 0:
            return
        if self.active == False:
            return
        c = self.builder.get_object(f"tab{nb.get_current_page()}.action")
        if c is not None:
            self.cmd.abort()
            self.cmd.mode(linuxcnc.MODE_MDI)
            self.cmd.wait_complete()
            c.emit('clicked')

def get_handlers(halcomp,builder,useropts):

    global debug
    for cmd in useropts:
        print(cmd)
        exec(cmd, globals())

    set_debug(debug)
    return [HandlerClass(halcomp,builder,useropts)]
