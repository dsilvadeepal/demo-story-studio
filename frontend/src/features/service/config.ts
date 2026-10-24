import type {PageSpec,ChartSpec} from '../../shared/pageTypes';
const common:ChartSpec[]=[{title:'Cases by priority',metric:'created_cases',dimension:'priority',kind:'donut'},{title:'Open cases by type and division',metric:'open_cases',dimension:'type_division',kind:'bubble'}];
export const servicePages:Record<string,PageSpec>={
 trend:{title:'Service trends',subtitle:'Understand demand, resolution, and the shape of your support workload.',kpis:['created_cases','closed_cases','close_days'],charts:[{title:'Weekly case volume by source',metric:'created_cases',dimension:'week_origin',kind:'stacked',wide:true},...common],records:'cases'},
 breakdown:{title:'Service breakdown',subtitle:'Follow the workload from the team overview to individual cases.',kpis:['created_cases','closed_cases','close_days'],charts:[{title:'Case breakdown by owner',metric:'created_cases',dimension:'owner',kind:'table',wide:true},...common],records:'cases'}
};
