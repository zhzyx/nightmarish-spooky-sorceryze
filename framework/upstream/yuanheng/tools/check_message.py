"""Optional program-side JSON contract check, never an authorization check."""
from pathlib import Path
import json,sys
import jsonschema
ROOT=Path(__file__).resolve().parents[1]
def pairs(items):
    value={}
    for key,item in items:
        if key in value:raise ValueError('Duplicate key: '+key)
        value[key]=item
    return value
def invalid(value):raise ValueError('Invalid constant: '+value)
def check(filename):
    with open(filename,'rb') as source:data=source.read(1048577)
    if len(data)>1048576:raise ValueError('Message exceeds 1 MiB')
    message=json.loads(data.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)
    schema=json.loads((ROOT/'contracts/message.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator(schema).validate(message)
    return message
if __name__=='__main__':
    try:
        if len(sys.argv)!=2:raise ValueError('Usage: check_message.py FILE')
        check(sys.argv[1]);print('valid JSON contract; authority not checked')
    except (ValueError,OSError,jsonschema.ValidationError) as error:
        print(str(error),file=sys.stderr);sys.exit(2)
