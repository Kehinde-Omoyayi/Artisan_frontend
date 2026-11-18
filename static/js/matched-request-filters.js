/* Four custom pickers on the compact matching-request search bar. */
(() => {
  const form = document.querySelector('[data-matched-filters]');
  if (!form) return;
  let catalogue;
  try { catalogue = JSON.parse(document.getElementById('matched-filter-catalogue')?.textContent || '{}'); }
  catch (_) { catalogue = {}; }
  /* The world list is a 2.4 MB static file, fetched the first time a location
     filter is opened instead of riding along with the page. */
  let geography = catalogue.geography || {};
  const geographyUrl = form.dataset.geographyUrl || '';
  const rows = Object.fromEntries([...form.querySelectorAll('[data-match-pick]')].map(row => [row.dataset.matchPick, row]));
  const placeholders = {service_name:'Any service',location_country:'Any country',location_area:'Any area',urgency:'Any urgency'};
  const urgency = [['LOW','Low'],['NORMAL','Normal'],['HIGH','High'],['EMERGENCY','Emergency']];
  const urgencyLabels = Object.fromEntries(urgency);
  const value = key => rows[key]?.querySelector('input[type=hidden]')?.value || '';
  const unique = items => [...new Set(items.filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  const set = (key, next, label) => {
    const row = rows[key]; if (!row) return;
    row.querySelector('input[type=hidden]').value = next || '';
    const text = label || urgencyLabels[next] || next || placeholders[key];
    row.querySelector('.match-pick-value').textContent = text;
    row.querySelector('.match-pick-toggle').title = text;
    row.classList.toggle('has-value',Boolean(next));
  };
  const close = () => Object.values(rows).forEach(row=>{
    row.classList.remove('is-open');
    row.querySelector('.match-pick-toggle').setAttribute('aria-expanded','false');
    row.querySelector('.match-pick-panel').hidden = true;
  });
  const choose = (key,next,label) => {
    set(key,next,label);
    if (key==='location_country') set('location_area','');
    close(); rows[key].querySelector('.match-pick-toggle').focus();
  };
  const options = key => {
    if (key==='urgency') return urgency;
    if (key==='service_name') return unique((catalogue.services || []).map(item=>item.name)).map(name=>[name,name]);
    if (key==='location_country') return unique(Object.keys(geography).concat(value(key))).map(name=>[name,name]);
    if (key==='location_area') {
      const country = value('location_country');
      if (!country) return [];
      return unique(Object.values(geography[country] || {}).flat().concat(value(key))).map(name=>[name,name]);
    }
    return [];
  };
  const render = key => {
    const row=rows[key], list=row.querySelector('.match-pick-options'), search=row.querySelector('.match-pick-search'), message=row.querySelector('.match-pick-message');
    const query=search.value.trim().toLocaleLowerCase();
    const matches=options(key).filter(pair=>pair[1].toLocaleLowerCase().includes(query));
    list.replaceChildren();
    // Every catalogue value is searchable. Limit DOM work for large countries;
    // filtering is done against the complete list, never just the first page.
    matches.slice(0,250).forEach(([id,label])=>{
      const button=document.createElement('button');button.type='button';button.textContent=label;
      button.setAttribute('aria-pressed',String(value(key)===id));
      button.addEventListener('click',()=>choose(key,id,label));list.appendChild(button);
    });
    message.hidden=matches.length>0 && matches.length<=250;
    if (key==='location_area' && !value('location_country')) {
      message.hidden=false;
      message.textContent='Choose a country first.';
    } else {
      message.textContent=matches.length>250 ? `${matches.length.toLocaleString()} options. Showing the first 250; type to narrow the full list.` : 'No options match your search.';
    }
  };
  Object.entries(rows).forEach(([key,row])=>{
    set(key,value(key));
    row.querySelector('.match-pick-toggle').addEventListener('click',()=>{
      const opening=!row.classList.contains('is-open');close();if(!opening)return;
      const show=()=>{
        row.classList.add('is-open');row.querySelector('.match-pick-toggle').setAttribute('aria-expanded','true');row.querySelector('.match-pick-panel').hidden=false;
        render(key);
      };
      if(!Object.keys(geography).length&&geographyUrl&&window.GeographySource){
        window.GeographySource.load(geographyUrl).then(src=>{geography=(src&&src.tree)||{};}).catch(()=>{}).finally(show);
      } else if(key==='location_area'&&geographyUrl&&window.GeographySource){
        window.GeographySource.areas(geographyUrl,value('location_country')||'').then(()=>show()).catch(()=>show());
      } else show();
    });
    row.querySelector('.match-pick-search').addEventListener('input',()=>render(key));
    row.querySelector('.match-pick-search').addEventListener('keydown',event=>{if(event.key==='Enter')event.preventDefault();});
    row.querySelector('.match-pick-clear').addEventListener('click',()=>choose(key,''));
  });
  form.querySelector('.match-filter-disclosure')?.addEventListener('toggle',event=>{if(!event.target.open)close();});
  document.addEventListener('click',event=>{if(!event.target.closest('[data-match-pick]'))close();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){const opened=form.querySelector('.match-pick.is-open');close();opened?.querySelector('.match-pick-toggle').focus();}});
})();
