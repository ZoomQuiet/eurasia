def load(filename, **args):
    file = open(filename, 'r')
    code = file.read()
    file.close()
    code = restricted(code)
    module = imp.new_module('<string>')
    default = {'__builtins__': {}}
    default.update(args)
    module.__dict__.update(default)
    exec code in module.__dict__
    return module

def restricted(code):
    _ = black(white('', code))
    if _:
        raise SyntaxError('invalid statement "%s"' \
            % _.groups()[0].strip())
    return code

import imp, re
black = re.compile(( r'((?:^|[\s])(?:import|from|as|with|'
    r'def|lambda|class|if|for|while|print|exec)[\s\\():]|'
    r'[^\w\s=()\-[\]{},#])')).search
white = re.compile(( r'(?:"(?:(?:\\\\)?(?:\\")?[^"]?)*")?'
    r"(?:'(?:(?:\\\\)?(?:\\')?[^']?)*')?")).sub; del re
