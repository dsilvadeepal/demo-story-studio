from langchain_core.tools import StructuredTool
from ..scenarios.repository import digest
from .contracts import ToolObservation
from .tools import SCHEMAS,DESCRIPTIONS,execute


def invoke_tool(context,name,arguments):
    if name not in SCHEMAS:return ToolObservation(tool=name,error='UNKNOWN_TOOL')
    try:
        args=SCHEMAS[name].model_validate(arguments)
        data=execute(context,name,args)
        evidence=digest(dict(run=context.run_id,dataset=context.dataset_id,tool=name,args=args.model_dump(mode='json'),data=data))
        return ToolObservation(tool=name,evidence_id=evidence,data=data)
    except (ValueError,LookupError) as error:
        # Only fixed server-owned hints may enter model context; never echo inputs.
        hint=str(error) if str(error) in ('Confirm explicit record IDs or top-N scope','Use industry-specific page titles, not generic page names','Page titles must retain canonical Sales/Service meaning','Inspect current vocabulary and cover every source category exactly','Industry adaptation requires explicit whole-dataset scope') else None
        return ToolObservation(tool=name,error='INVALID_TOOL_ARGUMENTS',data={'hint':hint} if hint else {})
    except Exception:return ToolObservation(tool=name,error='TOOL_UNAVAILABLE')


def build_tools(context):
    def wrapper(name):
        def call(**kwargs):return invoke_tool(context,name,kwargs).model_dump(mode='json')
        return call
    return [StructuredTool.from_function(func=wrapper(name),name=name,description=DESCRIPTIONS[name],args_schema=schema) for name,schema in SCHEMAS.items()]
