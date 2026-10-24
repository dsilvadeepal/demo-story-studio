export type ChartSpec={title:string;metric:string;dimension:string;kind:'bar'|'line'|'donut'|'scatter'|'bubble'|'stacked'|'table';wide?:boolean;ignorePeriod?:boolean;periodField?:'created_at'|'close_date'|'closed_date';openOnly?:boolean;description?:string};
export type PageSpec={title:string;subtitle:string;kpis:string[];charts:ChartSpec[];records?:'opportunities'|'cases'};
