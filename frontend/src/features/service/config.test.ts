import {it,expect} from 'vitest';
import {servicePages} from './config';
it('covers weekly trend and owner breakdown with case evidence',()=>{
 expect(Object.keys(servicePages)).toEqual(['trend','breakdown']);
 expect(servicePages.trend.charts.some(x=>x.dimension==='week_origin')).toBe(true);
 expect(servicePages.breakdown.charts.some(x=>x.dimension==='owner')).toBe(true);
 expect(servicePages.trend.kpis).toEqual(['created_cases','closed_cases','close_days']);
 expect(servicePages.breakdown.records).toBe('cases');
});
