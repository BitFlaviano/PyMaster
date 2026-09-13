import sys; sys.path.insert(0,'.')
from app.engine import sandbox

r = sandbox.run_code('print("Ola mundo")')
print('simples:', r['ok'], repr(r['output']), r.get('error'))

r2 = sandbox.run_code('x = 10; x += 5; print(x)')
print('calc:', r2['ok'], repr(r2['output']))

r3 = sandbox.run_code('print(1/0)')
print('erro:', r3['error'])

r4 = sandbox.run_code('import os; print(os.getcwd())')
print('import bloqueado:', r4['error'])

r5 = sandbox.run_code('nome = input("Nome: "); print(f"Oi {nome}")', stdin='Ana')
print('stdin:', r5['ok'], repr(r5['output']))

r6 = sandbox.run_code('while True: pass')
print('loop infinito timeout:', r6.get('timeout'))

r7 = sandbox.run_code('print("a")\nprint("b")\nprint("c")', visualize=True)
print('steps:', len(r7['steps']))
print('output:', repr(r7['output']))
