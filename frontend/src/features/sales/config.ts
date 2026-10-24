import type {PageSpec} from '../../shared/pageTypes';
export const salesPages:Record<string,PageSpec>={
 executive:{title:'Sales performance',subtitle:'A clear view of revenue, conversion, and the pipeline behind it.',kpis:['total_sales','win_rate','conversion','average_won_deal','won_cycle'],charts:[
 {title:'Pipeline generated',metric:'pipeline_generated',dimension:'month',kind:'line',ignorePeriod:true,description:'Created-date cohorts · full history; source excludes close-date filter'},
 {title:'Sales momentum',metric:'total_sales',dimension:'month',kind:'line',ignorePeriod:true,description:'Created-date cohorts · full history'},
 {title:'Win rate over time',metric:'win_rate',dimension:'month',kind:'line',ignorePeriod:true,description:'Won / all opportunities · created-date cohorts'},
 {title:'Value conversion over time',metric:'conversion',dimension:'month',kind:'line',ignorePeriod:true,description:'Won / closed amount · created-date cohorts'},
 {title:'Conversion by dimension',metric:'conversion',dimension:'account_type',kind:'bar',wide:true}]},
 pipeline:{title:'Pipeline analysis',subtitle:'Find where opportunity is building—and where it needs attention.',kpis:['pipeline_generated','open_opportunities','weighted_pipeline'],charts:[
 {title:'Weighted pipeline by days to close',metric:'weighted_pipeline',dimension:'days_bucket',kind:'scatter',ignorePeriod:true},
 {title:'Pipeline by stage',metric:'pipeline_generated',dimension:'stage',kind:'bar'},
 {title:'Weighted pipeline by account type',metric:'weighted_pipeline',dimension:'account_type',kind:'donut'},
 {title:'Weighted pipeline by owner',metric:'weighted_pipeline',dimension:'owner',kind:'bar'}]},
 detail:{title:'Opportunity detail',subtitle:'Explore the deals and relationships behind your pipeline.',kpis:[],charts:[{title:'Opportunities by expected close date',metric:'weighted_pipeline',dimension:'close_date',kind:'scatter',wide:true,ignorePeriod:true,openOnly:true}],records:'opportunities'}
};
