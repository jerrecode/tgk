"""KV indentation / widget parser: intentionally supports a documented subset.
No arbitrary eval of properties; event expressions are restricted to calls on
app, root, self and root.ids, and intended only for trusted project KV files.
"""
from __future__ import annotations
import ast
from pathlib import Path
from . import widgets as widgets

class _Factory:
    def __init__(self):self.classes={}
    def register(self,name,cls=None,**kwargs):
        cls=cls or kwargs.get('cls')
        if cls is None:raise ValueError('register(name, cls=...) required')
        self.classes[name]=cls
    def get(self,name):
        result=self.classes.get(name, getattr(widgets,name,None))
        if result is None:
            pending=list(widgets.Widget.__subclasses__())
            while pending:
                candidate=pending.pop()
                if candidate.__name__==name:result=candidate;break
                pending.extend(candidate.__subclasses__())
        if not isinstance(result,type) or not issubclass(result,widgets.Widget):
            raise ValueError(f'Unknown/unsupported KV widget class: {name}')
        return result
Factory=_Factory()

class KVError(ValueError):pass

class _Ids(dict):
    def __getattr__(self,key):
        try:return self[key]
        except KeyError as exc:raise AttributeError(key) from exc


def _eval_property(src,app,root,self_widget):
    try:return ast.literal_eval(src)
    except (ValueError,SyntaxError):pass
    # Only ordinary attribute paths, no general Python execution for properties.
    tree=ast.parse(src,mode='eval').body
    def resolve(n):
        if isinstance(n,ast.Name) and n.id in ('app','root','self'):
            return {'app':app,'root':root,'self':self_widget}[n.id]
        if isinstance(n,ast.Attribute) and not n.attr.startswith('_'):
            return getattr(resolve(n.value),n.attr)
        raise KVError(f'Unsupported KV expression: {src!r}')
    return resolve(tree)

def _invoke_event(expr,app,root,self_widget):
    """Execute a zero- or one/multi-literal-argument call on app/root/self.
    Does NOT allow subscript, comprehensions, chained arbitrary function calls,
    private attrs, global names, builtins or imports.
    """
    tree=ast.parse(expr,mode='eval').body
    if not isinstance(tree,ast.Call) or tree.keywords:
        raise KVError('KV event must be a method call, e.g. app.submit(self)')
    def resolve(n):
        if isinstance(n,ast.Name) and n.id in ('app','root','self'):
            return {'app':app,'root':root,'self':self_widget}[n.id]
        if isinstance(n,ast.Attribute) and not n.attr.startswith('_'):
            return getattr(resolve(n.value),n.attr)
        raise KVError(f'Unsupported event argument: {expr!r}')
    if not isinstance(tree.func,ast.Attribute):
        raise KVError('KV callbacks must be method calls')
    base=resolve(tree.func.value)
    fn=getattr(base,tree.func.attr)
    if tree.func.attr.startswith('_') or not callable(fn):
        raise KVError('Private/non-callable event target')
    args=[]
    for arg in tree.args:
        try:args.append(ast.literal_eval(arg))
        except (ValueError,SyntaxError):args.append(resolve(arg))
    return fn(*args)

class _Builder:
    def __init__(self):self.rules={}
    def load_file(self,filename,**kwargs):
        return self.load_string(Path(filename).read_text(encoding='utf-8'),**kwargs)
    def load_string(self,kv,**kwargs):
        lines=kv.splitlines()
        roots=[];rule_name=None;rule_lines=[]
        def save_rule():
            if rule_name is not None:
                if rule_name in self.rules:raise KVError('duplicate KV class rule: '+rule_name)
                self.rules[rule_name]='\n'.join(rule_lines)
        for number,line in enumerate(lines,1):
            clean=line.strip()
            if clean.startswith('#:kivy '):continue
            if clean.startswith('#:'):
                raise KVError(f'line {number}: unsupported KV directive {clean!r}')
            if line and not line[0].isspace() and clean.startswith('<') and clean.endswith('>:'):
                save_rule()
                rule_name=clean[1:-2]
                if not rule_name.isidentifier():raise KVError('invalid KV rule name')
                rule_lines=[]
            elif rule_name is not None and (not clean or line[0].isspace()):
                rule_lines.append(line)
            else:
                if rule_name is not None:save_rule();rule_name=None;rule_lines=[]
                roots.append(line)
        save_rule()
        if not any(line.strip() for line in roots):return None
        return self._parse('\n'.join(roots))
    def apply(self,widget):
        name=type(widget).__name__
        if name in self.rules:
            self._parse(name+':\n'+self.rules[name],existing_root=widget)
    def _parse(self,kv,existing_root=None):
        from .widgets import App
        app=App.get_running_app()
        stack=[];root=None;ids=_Ids();events=[];rule=None
        for lineno,line in enumerate(kv.splitlines(),1):
            if not line.strip() or line.lstrip().startswith('#'):continue
            # Explicitly refuse nontrivial KV directives rather than ignoring them.
            if line.lstrip().startswith(('#:','<', '@')):
                raise KVError(f'line {lineno}: template rules/directives are unsupported in this version')
            indent=len(line)-len(line.lstrip(' '))
            if '\t' in line[:len(line)-len(line.lstrip())]:raise KVError('Use spaces for KV indentation')
            item=line.strip()
            if ':' not in item:raise KVError(f'line {lineno}: missing colon')
            head,tail=item.split(':',1)
            key=head.strip();tail=tail.strip()
            if key and key[0].isupper() and not tail:
                while stack and indent<=stack[-1][0]:stack.pop()
                if existing_root is not None and root is None and not stack:
                    if type(existing_root).__name__!=key:raise KVError('rule/root class mismatch')
                    node=existing_root
                else:node=Factory.get(key)()
                if stack:stack[-1][1].add_widget(node)
                elif root is None:root=node
                else:raise KVError(f'line {lineno}: multiple KV roots')
                stack.append((indent,node))
                continue
            if not stack:raise KVError(f'line {lineno}: property without widget')
            if indent<=stack[-1][0]:raise KVError(f'line {lineno}: incorrect property indentation')
            node=stack[-1][1]
            if key=='id':
                if not tail.isidentifier() or tail.startswith('_') or tail in ids:
                    raise KVError(f'line {lineno}: invalid/duplicate id {tail!r}')
                ids[tail]=node
            elif key.startswith('on_'):
                events.append((node,key,tail))
            else:
                try:value=_eval_property(tail,app,root,node)
                except Exception as exc:raise KVError(f'line {lineno}: {key}: {exc}') from exc
                setattr(node,key,value)
        if root is None:raise KVError('KV text has no root widget')
        root.ids.update(ids)
        for node,name,expr in events:
            node.bind(**{name:lambda _sender,*_,expr=expr,node=node:
                       _invoke_event(expr,App.get_running_app(),root,node)})
        return root
Builder=_Builder()
