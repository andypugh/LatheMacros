#!/usr/bin/env python
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
import gtk
import glib
import linuxcnc

debug = 0


class HandlerClass:

    def on_destroy(self,obj,data=None):
        print 'Destroy?'
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
                           IniFile.widgets : widget_defaults(select_widgets(self.builder.get_objects(), hal_only=False,output_only = True))
                        }
        self.ini = IniFile(self.ini_filename,self.defaults,self.builder)
        self.ini.restore_state(self)
        
    def spin_handler(self, obj, data=None):
        data = obj.get_text()
        if data[-3:] == 'tpi':
            obj.set_value(25.4/float(data[:-3]))
            obj.set_position(-1)
        elif data[-2:] == 'in':
            obj.set_value(25.4*float(data[:-2]))
            obj.set_position(-1)
        elif data[-2:] == 'mm':
            obj.set_value(float(data[:-2])/25.4)
            obj.set_position(-1)
        elif data[-5:] == 'pitch':
            obj.set_value(25.4/float(data[:-5]))
            obj.set_position(-1)
        elif data[-2:] in [ '/2', '/4', '/8']:
            v = data[:-2].split()
            if len(v) == 2:
                obj.set_value(float(v[0]) + float(v[1]) / float(data[-1:]))
                obj.set_position(-1)
            elif len(v) == 1:
                obj.set_value(float(v[0]) / float(data[-1:]))
                obj.set_position(-1)
        elif data[-3:] in [ '/16', '/32', '/64']:
            v = data[:-3].split()
            if len(v) == 2:
                obj.set_value(float(v[0]) + float(v[1]) / float(data[-2:]))
                obj.set_position(-1)
            elif len(v) == 1:
                obj.set_value(float(v[0]) / float(data[-2:]))
                obj.set_position(-1)

def get_handlers(halcomp,builder,useropts):

    global debug
    for cmd in useropts:
        exec cmd in globals()

    set_debug(debug)
    return [HandlerClass(halcomp,builder,useropts)]


