

from Tkinter import *

from tkSimpleDialog import Dialog
from shtoom.Options import NoDefaultOption


class PreferencesDialog(Dialog):
    def __init__(self, parent, main, opts):
        self.main = main
        self.opts = opts
        self.options = {}
        self.choiceoptions = {}
        self.booloptions = {}
        Dialog.__init__(self, parent, title="Preferences")

    def body(self, parent):
        import notebook
        notebook = notebook.notebook(parent, side=TOP)
        for group in self.opts:
            tab = Frame(notebook())
            for optnumber, option in enumerate(group):
                optf = Frame(tab)
                label = Label(optf, text=option.getPrettyName())
                label.pack(fill=Y, side=LEFT)
                if option.optionType in ( 'String', 'Number', 'Password' ):
                    if option.optionType == 'Password':
                        edit = Entry(optf, show='*')
                    else:
                        edit = Entry(optf)
                    val = option.getValue()
                    if val and val is not NoDefaultOption:
                        edit.insert(0,str(val))
                    edit.pack(fill=BOTH, side=RIGHT)
                    get = edit.get
                    edit = ( optf, label, edit )
                elif option.optionType == 'Choice':
                    rbf = Frame(optf)
                    buttons = []
                    name = option.getName()
                    val = option.getValue()
                    self.choiceoptions[name] = val
                    for c in option.getChoices():
                        if c == val:
                            E = 1 
                        else:
                            E = 0 
                        b = Radiobutton(rbf, text=c, indicatoron=1, 
                                        variable=self.choiceoptions[name], 
                                        value=c, 
                                        command=lambda o=self.choiceoptions, n=name, c=c: o.__setitem__(n,c) )
                        if E: 
                            b.select()
                        else:
                            b.deselect()
                        b.pack(side=LEFT)
                        buttons.append(b)
                    rbf.pack(side=RIGHT, fill=BOTH)
                    get = lambda opt=name: self.choiceoptions[opt]
                    edit = ( rbf, buttons )
                elif option.optionType == 'Boolean':
                    name = option.getName()
                    val = option.getValue()
                    self.booloptions[name] = val
                    b = Checkbutton(optf, variable=self.booloptions[name],
                                    command=lambda o=self.booloptions, n=name: o.__setitem__(n, not o[n]) )
                    b.pack(side=RIGHT, fill=BOTH)
                    edit = b
                    get = lambda opt=name: self.booloptions[opt]
                else: 
                    raise ValueError, "unknown option type %s"%(option.optionType)
                optf.pack(fill=X, side=TOP)
                if edit is not None:
                    self.options[option.getName()] = ( option.optionType, get, edit )
            notebook.add_screen(tab, group.getName())
        return notebook()
        
    def apply(self):
        out = {}
        for o, (t,get,edit)  in self.options.items():
            v = get()
            if v is not NoDefaultOption:
                out[o] = v
        self.main.updateOptions(out)
