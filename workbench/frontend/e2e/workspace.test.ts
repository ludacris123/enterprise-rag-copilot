import {test,expect} from '@playwright/test';

test('authenticated workspace completes RAG, approval, evaluation, and ML flows',async({page})=>{
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('/');await page.getByLabel('Email address').fill('browser-ci@example.com');
 await page.getByLabel('Password',{exact:true}).fill('BrowserTest123!');await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.locator('#workspace-select')).not.toHaveValue('');
 await page.getByRole('button',{name:'Knowledge',exact:true}).click();
 await page.locator('input[type=file]').setInputFiles({name:'policy.md',mimeType:'text/markdown',buffer:Buffer.from('Customers may request a refund within 30 days. Travel claims must be submitted within 14 days.')});
 await expect(page.getByText('ready',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'RAG workspace',exact:true}).click();
 await page.getByLabel('Ask a question').fill('What is the refund window?');await page.getByRole('button',{name:'Run question'}).click();
 await expect(page.getByText('Citation IDs checked',{exact:true})).toBeVisible();await expect(page.locator('.answer-body')).toContainText('30 days');
 await page.reload();await expect(page.locator('#workspace-select')).not.toHaveValue('');
 await page.locator('.history-item').first().click();await expect(page.getByText('Citation IDs checked',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Agent runs',exact:true}).click();await page.getByLabel('Propose saving a note').check();
 await page.getByLabel('Ask a question').fill('What is the refund window?');await page.getByRole('button',{name:'Run question'}).click();
 await page.getByRole('button',{name:'Approve note',exact:true}).click();await expect(page.getByText('approved',{exact:true}).first()).toBeVisible();
 await page.getByRole('button',{name:'Evaluations',exact:true}).click();await page.getByRole('button',{name:'Save dataset',exact:true}).click();
 await page.getByRole('button',{name:'Run evaluation',exact:true}).click();await expect(page.getByText('pass rate',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'ML experiments',exact:true}).click();
 const csv='length,width,target\n'+Array.from({length:100},(_,i)=>`${i%10+1},${i%7+1},${i%10>4?'large':'small'}`).join('\n');
 await page.getByLabel('Dataset CSV').setInputFiles({name:'sample.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});
 await page.getByLabel('Target column').fill('target');await page.getByRole('button',{name:'Train model',exact:true}).click();
 await expect(page.getByText('accuracy',{exact:true})).toBeVisible();
 await page.getByLabel('Prediction rows · JSON').fill('[{"length":8,"width":3}]');await page.getByRole('button',{name:'Predict',exact:true}).click();
 await expect(page.locator('pre').filter({hasText:'predictions'})).toContainText('large');
 await page.getByRole('button',{name:'Observability',exact:true}).click();await expect(page.getByText('extractive-v1',{exact:true}).first()).toBeVisible();
 await page.getByRole('button',{name:'Workspace settings',exact:true}).click();await expect(page.getByText('agent.approve',{exact:true})).toBeVisible();
 for(const width of [390,768,1440]){
  await page.setViewportSize({width,height:900});
  for(const tab of ['RAG workspace','Knowledge','Agent runs','Evaluations','ML experiments','Model lab','Observability','Workspace settings']){
   await page.getByRole('button',{name:tab,exact:true}).click();await expect(page.getByRole('heading',{name:tab,exact:true})).toBeVisible();
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${tab} at ${width}px`).toBeTruthy();
  }
 }
 expect(errors).toEqual([]);
 await page.setViewportSize({width:1440,height:1000});await page.getByRole('button',{name:'Sign out',exact:true}).first().click();
 await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();
});
