import {it,expect} from 'vitest';
import {salesPages} from './config';
it('covers three Sales pages with defined data bindings',()=>{
 expect(Object.keys(salesPages)).toEqual(['executive','pipeline','detail']);
 expect(salesPages.executive.kpis).toEqual(['total_sales','win_rate','conversion','average_won_deal','won_cycle']);
 expect(salesPages.executive.charts.filter(x=>x.dimension==='month')).toHaveLength(4);
 expect(salesPages.pipeline.charts.some(x=>x.dimension==='days_bucket')).toBe(true);
 expect(salesPages.detail.records).toBe('opportunities');
});
it('only days-to-close Pipeline chart excludes the selected created-date period',()=>{
 expect(salesPages.pipeline.charts.filter(x=>x.ignorePeriod).map(x=>x.dimension)).toEqual(['days_bucket']);
});
