import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {ReviewPanel} from './ReviewPanel';
afterEach(cleanup);
it('shows actual comparison, date warnings, and offers one approval-and-apply action',()=>{
 const approve=vi.fn(),apply=vi.fn();
 render(<ReviewPanel candidate={{id:'candidate',parent_id:'base',revision:2,content_hash:'hash',as_of_date:'2027-01-01',status:'preview'}} comparison={{current_id:'base',candidate_id:'candidate',metric_deltas:{total_sales:{before:'100',after:'110',delta:'10'}},changed_counts:{price:3},warnings:['As-of shifts across Sales and Service'],selection_summary:{domain:'sales',count:1,global:false}} as any} approvalId={null} busy={false} onReview={vi.fn()} onApprove={approve}/>);
 expect(screen.getByText('Resolved scope: 1 sales records')).toBeTruthy();
 expect(screen.getByText(/As-of shifts/)).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:/Approve & apply revision/}));expect(approve).toHaveBeenCalledOnce();expect(apply).not.toHaveBeenCalled();
 expect(screen.queryByRole('button',{name:'Apply approved revision'})).toBeNull();
});
it('reviews rules and linked samples, blocks failed validation, and keeps details secondary',()=>{
 const onReview=vi.fn();
 const props={candidate:{id:'candidate',parent_id:'base',revision:2,content_hash:'hash',as_of_date:'2027-01-01',status:'preview' as const},approvalId:null,busy:false,onReview,onApprove:vi.fn()};
 render(<ReviewPanel {...props} comparison={{current_id:'base',candidate_id:'candidate',metric_deltas:{},changed_counts:{},warnings:['Review wording'],review_summary:{parent_id:'base',industry:'Manufacturing',counts:{opportunities:1200},rules:{company_descriptor:'Engineering',opportunity_template:'{family} contract {number}',families:[{source:'Office',target:'Pumps'}],case_subjects:[],page_titles:{executive:'Manufacturing sales overview'}},checks:[{label:'Protected fields preserved',passed:false}],examples:[{opportunity_id:'o1',chain:[{kind:'opportunities',id:'o1',before:'Office deal',after:'Pumps contract'}]},{opportunity_id:'o2',chain:[{kind:'opportunities',id:'o2',before:'Retail deal',after:'Plant contract'}]}]}}}/>);
 expect(screen.getByText('1,200')).toBeTruthy();
 expect(screen.getByText('Pumps contract')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Example 2'}));expect(screen.getByText('Plant contract')).toBeTruthy();
 expect((screen.getByRole('button',{name:/Approve & apply revision/}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('Review note or requested change'),{target:{value:'Revise the wording'}});
 fireEvent.click(screen.getByRole('button',{name:'Request changes'}));expect(onReview).toHaveBeenCalledWith('edit','Revise the wording');
 expect(screen.getByText('More review actions').closest('details')?.open).toBe(false);
});
