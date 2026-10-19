(function(){
  const apiErrors=window.ArtisanApiErrors;
  const formatApiError=(payload,status,options)=>apiErrors?apiErrors.format(payload,status,options):"The request could not be completed. Please try again.";
  const readApiPayload=(response)=>apiErrors?apiErrors.readResponse(response):response.json().catch(()=>null);
  const stream=document.getElementById("conversation-stream");
  if(!stream)return;
  const id=stream.dataset.conversationId;
  const form=document.getElementById("conversation-message-form");
  const input=form?.querySelector("textarea[name=body]");
  const fileInput=document.getElementById("conversation-attachments");
  const preview=document.getElementById("attachment-preview");
  const statusNode=document.getElementById("chat-status");
  const unreadNode=document.getElementById("chat-unread-count");
  const assistantNode=document.getElementById("conversation-assistant");
  const suggestionsNode=document.getElementById("chat-suggestions");
  const assistantOptionsNode=document.getElementById("request-assistant-options");
  const requestAssistantDetails=document.getElementById("request-assistant-card");
  const assistantEnabled=stream.dataset.assistantEnabled==="true";
  const workspace=document.querySelector(".chat-workspace");
  const scrollArea=document.getElementById("conversation-scroll-area")||stream;
  const csrf=form?.querySelector("input[name=csrfmiddlewaretoken]")?.value||document.querySelector('meta[name="csrf-token"]')?.content||"";
  const viewerId=Number(stream.dataset.viewerId||0);
  const role=stream.dataset.role||"";
  let delay=4000,timer=0,lastSignature="",firstPayload=true,readPending=false,sendingMessage=false;
  let selectedFiles=Array.from(fileInput?.files||[]);
  let assistantContext=null;
  try{assistantContext=JSON.parse(assistantOptionsNode?.textContent||"null");}catch(_){assistantContext=null;}
  const seenMessageIds=new Set();

  const setStatus=(text)=>{if(statusNode)statusNode.textContent=text;};
  const safeUrl=(value)=>{
    try{
      const parsed=new URL(value,window.location.origin);
      return parsed.protocol==="https:"||parsed.protocol==="http:"?parsed.href:"";
    }catch(_){return "";}
  };
  const localDateTimeValue=(value)=>{
    const date=new Date(value);
    if(Number.isNaN(date.getTime()))return "";
    const pad=(number)=>String(number).padStart(2,"0");
    return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  };
  const assistantValues=(context=assistantContext)=>context?.request_state?.values&&typeof context.request_state.values==="object"?context.request_state.values:{};
  const pad2=(value)=>String(value).padStart(2,"0");
  function formatClock(value){
    const match=String(value||"").match(/^(\d{1,2}):(\d{2})/);
    if(!match)return "";
    const hour=Number(match[1]);
    const minute=match[2];
    if(hour>23)return "";
    return `${hour%12||12}:${minute} ${hour>=12?"pm":"am"}`;
  }
  function formatSchedule(dateValue,timeStart,timeEnd,timeNote){
    const match=String(dateValue||"").match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if(!match)return "";
    const dateText=`${match[3]}-${match[2]}-${match[1]}`;
    const start=formatClock(timeStart);
    const end=formatClock(timeEnd);
    const times=start&&end?`${start}–${end}`:start||end;
    const note=String(timeNote||"").trim();
    return `${dateText}${times?`, ${times}`:""}${note?` · ${note}`:""}`;
  }
  function updateScheduleSummary(context=assistantContext){
    const target=assistantNode?.querySelector("#assistant-schedule-summary");
    if(!target)return;
    const values=assistantValues(context);
    const summary=formatSchedule(values.preferred_date,values.preferred_time_start,values.preferred_time_end,values.preferred_time_note);
    target.hidden=!summary;
    target.textContent=summary?`Saved preference: ${summary}. This is not a confirmed appointment.`:"";
  }
  function controlLabel(text,control){
    const label=document.createElement("label");
    label.className="assistant-control-label";
    const title=document.createElement("span");
    title.textContent=text;
    label.append(title,control);
    return label;
  }
  function addOption(select,value,label){
    const option=document.createElement("option");
    option.value=String(value??"");
    option.textContent=String(label??"");
    select.appendChild(option);
    return option;
  }
  function updateScheduleControlPreview(){
    if(!assistantNode)return;
    const host=assistantNode.querySelector("#assistant-controls");
    const date=host?.querySelector("[data-assistant-date]");
    const previewNode=host?.querySelector("[data-assistant-control-preview]");
    if(!date||!previewNode)return;
    const time=host.querySelector("[data-assistant-time]")?.value||"";
    const summary=formatSchedule(date.value,time,"","");
    previewNode.hidden=!summary;
    previewNode.textContent=summary?`Selected preference: ${summary}`:"Choose a future date; time is optional.";
  }
  function renderAssistantControls(context=assistantContext){
    const host=assistantNode?.querySelector("#assistant-controls");
    if(!host)return;
    host.replaceChildren();
    const field=String(context?.prompt?.field||"");
    const values=assistantValues(context);
    const options=context?.request_options||{};
    const group=document.createElement("div");
    group.className="assistant-control-group";
    let addButtonText="Add to message";

    if(field==="service"){
      const select=document.createElement("select");
      select.className="field-input";
      select.dataset.assistantService="";
      select.required=true;
      addOption(select,"","Choose a service from this artisan’s catalogue");
      const categories=Array.isArray(options.categories)?options.categories:[];
      categories.forEach(category=>{
        const services=Array.isArray(category.services)?category.services:[];
        if(!services.length)return;
        const optgroup=document.createElement("optgroup");
        optgroup.label=String(category.name||"Available services");
        services.forEach(service=>{
          const option=document.createElement("option");
          option.value=String(service.id??"");
          option.textContent=String(service.name||"");
          option.dataset.serviceName=String(service.name||"");
          optgroup.appendChild(option);
        });
        select.appendChild(optgroup);
      });
      if(!select.querySelector("option[data-service-name]"))return;
      group.appendChild(controlLabel("Service",select));
      addButtonText="Add service to message";
    }else if(field==="location"){
      const select=document.createElement("select");
      select.className="field-input";
      select.dataset.assistantLocation="";
      select.required=true;
      addOption(select,"","Choose a location from the available catalogue");
      const selectedService=String(values.service_id||"");
      const locations=Array.isArray(options.locations)?options.locations:[];
      const matching=locations.filter(location=>!selectedService||!Array.isArray(location.service_ids)||location.service_ids.map(String).includes(selectedService));
      matching.forEach(location=>{
        const label=location.label||`${location.area||""}, ${location.state||""}, ${location.country||""}`;
        addOption(select,location.id,label);
      });
      if(!matching.length)return;
      group.appendChild(controlLabel("Service location",select));
      addButtonText="Add location to message";
    }else if(field==="preferred_date"){
      const date=document.createElement("input");
      date.type="date";
      date.className="field-input";
      date.dataset.assistantDate="";
      date.required=true;
      date.min=document.querySelector('#request-assistant-form [name="preferred_date"]')?.min||stream.dataset.assistantToday||"";
      date.value=String(values.preferred_date||"");
      const time=document.createElement("input");
      time.type="time";
      time.className="field-input";
      time.dataset.assistantTime="";
      time.value=String(values.preferred_time_start||"").slice(0,5);
      const controls=document.createElement("div");
      controls.className="assistant-control-grid";
      controls.append(controlLabel("Preferred date",date),controlLabel("Preferred time · optional",time));
      group.appendChild(controls);
      const selected=document.createElement("p");
      selected.className="assistant-control-preview";
      selected.dataset.assistantControlPreview="";
      selected.setAttribute("aria-live","polite");
      group.appendChild(selected);
      addButtonText="Add date and time to message";
    }else if(field==="budget"){
      const budget=document.createElement("input");
      budget.type="number";
      budget.className="field-input";
      budget.min="0";
      budget.step="0.01";
      budget.inputMode="decimal";
      budget.required=true;
      budget.dataset.assistantBudget="";
      budget.value=String(values.budget||"");
      budget.placeholder="Enter an amount in naira";
      group.appendChild(controlLabel("Budget · optional",budget));
      addButtonText="Add budget to message";
    }else{
      return;
    }

    const note=document.createElement("p");
    note.className="assistant-control-note";
    note.textContent="This adds a clear reply to the message box; review it and press Send to save it in the conversation.";
    const button=document.createElement("button");
    button.type="button";
    button.className="assistant-control-add";
    button.dataset.assistantControlAdd=field;
    button.textContent=addButtonText;
    host.append(group,note,button);
    updateScheduleControlPreview();
  }
  document.querySelectorAll('input[type="datetime-local"][data-utc-value]').forEach(field=>{
    const value=localDateTimeValue(field.dataset.utcValue||"");
    if(value)field.value=value;
  });
  document.querySelectorAll(".workflow-local-time[data-utc-time]").forEach(node=>{
    const date=new Date(node.dataset.utcTime||"");
    if(Number.isNaN(date.getTime()))return;
    node.textContent=date.toLocaleString(undefined,{weekday:"short",day:"numeric",month:"short",year:"numeric",hour:"numeric",minute:"2-digit"});
  });

  function addControlReply(button){
    if(!input)return;
    const field=button.dataset.assistantControlAdd||"";
    const host=assistantNode?.querySelector("#assistant-controls");
    let reply="";
    if(field==="service"){
      const select=host?.querySelector("[data-assistant-service]");
      if(!select?.reportValidity())return;
      const selected=select.selectedOptions[0];
      reply=`I need ${selected?.dataset.serviceName||selected?.textContent||"this service"}.`;
    }else if(field==="location"){
      const select=host?.querySelector("[data-assistant-location]");
      if(!select?.reportValidity())return;
      reply=`The service location is ${select.selectedOptions[0]?.textContent||""}.`;
    }else if(field==="preferred_date"){
      const date=host?.querySelector("[data-assistant-date]");
      const time=host?.querySelector("[data-assistant-time]");
      if(!date?.reportValidity())return;
      if(time&&!time.checkValidity()){time.reportValidity();return;}
      const summary=formatSchedule(date.value,time?.value||"","","");
      if(!summary){setStatus("Choose a valid preferred date before adding it to your message.");return;}
      reply=`I prefer ${summary.replace(", "," at ")} for the service.`;
    }else if(field==="budget"){
      const amount=host?.querySelector("[data-assistant-budget]");
      if(!amount?.reportValidity())return;
      const number=Number(amount.value);
      if(!Number.isFinite(number)||number<0){setStatus("Enter a valid non-negative budget amount.");amount?.focus();return;}
      let formatted=String(amount.value);
      try{formatted=new Intl.NumberFormat("en-NG",{maximumFractionDigits:2}).format(number);}catch(_){formatted=String(amount.value);}
      reply=`My budget is ₦${formatted}.`;
    }
    if(!reply)return;
    const current=input.value.trim();
    const next=current?`${current}\n${reply}`:reply;
    if(input.maxLength>0&&next.length>input.maxLength){setStatus("The added detail would exceed the message length limit. Shorten your message and try again.");input.focus();return;}
    input.value=next;
    input.focus();
    input.setSelectionRange(input.value.length,input.value.length);
    setStatus("Added to your message. Review the wording, then press Send to update the request draft.");
  }

  workspace?.addEventListener("click",event=>{
    const target=event.target;
    const controlButton=target.closest?.("[data-assistant-control-add]");
    if(controlButton){addControlReply(controlButton);return;}
    const button=target.closest?.("[data-suggestion]");
    if(!button||!input)return;
    const suggestion=button.dataset.suggestion||button.textContent||"";
    if(/review.*request|request.*review/i.test(suggestion)&&requestAssistantDetails){
      requestAssistantDetails.open=true;
      requestAssistantDetails.scrollIntoView({behavior:"smooth",block:"center"});
      setStatus("Your draft is still unsent. Review or edit each detail, then submit only when ready.");
      return;
    }
    input.value=suggestion;
    input.focus();
  });
  workspace?.addEventListener("input",updateScheduleControlPreview);
  workspace?.addEventListener("change",updateScheduleControlPreview);
  if(assistantEnabled&&assistantContext){
    renderAssistantControls(assistantContext);
    updateScheduleSummary(assistantContext);
  }

  function makeAttachment(attachment){
    const url=safeUrl(attachment.url);
    if(!url)return null;
    const contentType=String(attachment.content_type||"file");
    if(contentType.toLowerCase().startsWith("image/")){
      const link=document.createElement("a");
      link.className="chat-attachment-image";
      link.href=url;
      link.target="_blank";
      link.rel="noopener";
      const image=document.createElement("img");
      image.src=url;
      image.alt="Shared photo; open full size";
      image.loading="lazy";
      link.appendChild(image);
      return link;
    }
    const link=document.createElement("a");
    link.className="chat-attachment-file";
    link.href=url;
    link.target="_blank";
    link.rel="noopener";
    link.textContent=`Attachment · ${contentType}`;
    return link;
  }

  function render(messages){
    const keepBottom=scrollArea.scrollHeight-scrollArea.scrollTop-scrollArea.clientHeight<120;
    const fragment=document.createDocumentFragment();
    messages.forEach(message=>{
      const article=document.createElement("article");
      const isMine=Number(message.sender_id)===viewerId;
      article.className="chat-message "+(message.message_type==="SYSTEM"?"system":isMine?"mine":"theirs");
      if(!isMine&&message.message_type!=="SYSTEM"){
        const avatar=document.createElement("span");
        avatar.className="chat-message-avatar";
        avatar.setAttribute("aria-hidden","true");
        const photo=safeUrl(stream.dataset.counterpartyAvatar||"");
        const fallback=document.createElement("span");
        fallback.dataset.profilePhotoFallback="";
        fallback.textContent=String(message.sender_name||"P").trim().slice(0,1).toUpperCase();
        fallback.hidden=Boolean(photo);
        avatar.appendChild(fallback);
        if(photo){
          const image=document.createElement("img");
          image.src=photo;
          image.alt="";
          image.loading="lazy";
          image.referrerPolicy="no-referrer";
          image.dataset.profilePhotoImage="";
          avatar.appendChild(image);
        }
        article.appendChild(avatar);
      }
      const bubble=document.createElement("div");
      bubble.className="chat-bubble";
      const who=document.createElement("strong");
      who.textContent=message.message_type==="SYSTEM"?"Artisan Market":isMine?"You":(message.sender_name||"Participant");
      bubble.appendChild(who);
      if(message.body){
        const body=document.createElement("p");
        body.textContent=message.body;
        bubble.appendChild(body);
      }
      (message.attachments||[]).forEach(attachment=>{
        const rendered=makeAttachment(attachment);
        if(rendered)bubble.appendChild(rendered);
      });
      const time=document.createElement("time");
      time.dateTime=String(message.created_at||"");
      const parsedDate=new Date(message.created_at);
      time.textContent=Number.isNaN(parsedDate.getTime())?String(message.created_at||""):parsedDate.toLocaleString();
      bubble.appendChild(time);
      article.appendChild(bubble);
      fragment.appendChild(article);
    });
    if(!messages.length){
      const empty=document.createElement("div");
      empty.className="empty chat-empty-state";
      empty.textContent="No messages yet. Start the conversation naturally — you can write a note or attach a photo.";
      fragment.appendChild(empty);
    }
    const assistantBubble=stream.querySelector("#conversation-assistant.request-assistant-message");
    if(assistantBubble)fragment.appendChild(assistantBubble);
    stream.replaceChildren(fragment);
    if(firstPayload||keepBottom)scrollArea.scrollTop=scrollArea.scrollHeight;
    firstPayload=false;
  }

  function readAssistantContext(parsedDocument){
    const node=parsedDocument?.getElementById("request-assistant-options");
    if(!node)return null;
    try{
      const parsed=JSON.parse(node.textContent||"null");
      return parsed&&typeof parsed==="object"?parsed:null;
    }catch(_){return null;}
  }

  function updateAssistant(parsedDocument){
    if(!assistantNode)return;
    const next=parsedDocument.getElementById("conversation-assistant");
    if(!next)return;
    const nextContext=readAssistantContext(parsedDocument);
    if(assistantNode.classList.contains("request-assistant-message")&&nextContext){
      const previousValues={...assistantValues(assistantContext)};
      assistantContext=nextContext;
      assistantNode.dataset.mode=String(nextContext.mode||"");
      const reply=assistantNode.querySelector("#assistant-reply");
      if(reply)reply.textContent=String(nextContext.reply||"");
      const prompt=nextContext.prompt&&typeof nextContext.prompt==="object"?nextContext.prompt:{};
      let questionWrap=assistantNode.querySelector("#assistant-question-wrap");
      if(prompt.field&&prompt.text){
        if(!questionWrap){
          questionWrap=document.createElement("div");
          questionWrap.className="assistant-question-wrap";
          questionWrap.id="assistant-question-wrap";
          const label=document.createElement("span");
          const question=document.createElement("p");
          question.id="assistant-question";
          questionWrap.append(label,question);
          assistantNode.querySelector(".assistant-bubble")?.appendChild(questionWrap);
        }
        const label=questionWrap.querySelector("span");
        const question=questionWrap.querySelector("#assistant-question");
        if(label)label.textContent=prompt.optional?"Optional detail":"Next detail";
        if(question)question.textContent=String(prompt.text);
      }else if(questionWrap){
        questionWrap.remove();
      }
      renderAssistantControls(nextContext);
      updateScheduleSummary(nextContext);
      window.dispatchEvent(new CustomEvent("artisan:assistant-state",{detail:{assistant:nextContext,previousValues}}));
      return;
    }
    const reply=assistantNode.querySelector("#assistant-reply");
    const nextReply=next.querySelector("#assistant-reply");
    if(reply&&nextReply)reply.textContent=nextReply.textContent;
    assistantNode.dataset.mode=next.dataset.mode||"";
    const nextQuestion=next.querySelector("#assistant-question");
    let questionWrap=assistantNode.querySelector("#assistant-question-wrap");
    if(nextQuestion){
      if(!questionWrap){
        questionWrap=document.createElement("div");
        questionWrap.className="assistant-question-wrap";
        questionWrap.id="assistant-question-wrap";
        const label=document.createElement("span");
        label.textContent="Next detail";
        const question=document.createElement("p");
        question.id="assistant-question";
        questionWrap.append(label,question);
        assistantNode.querySelector(".assistant-guidance-copy")?.appendChild(questionWrap);
      }
      const currentQuestion=questionWrap.querySelector("#assistant-question");
      const currentLabel=questionWrap.querySelector("span");
      const nextLabel=next.querySelector("#assistant-question-wrap span");
      if(currentQuestion)currentQuestion.textContent=nextQuestion.textContent;
      if(currentLabel&&nextLabel)currentLabel.textContent=nextLabel.textContent;
    }else if(questionWrap){
      questionWrap.remove();
    }
  }

  function updateSuggestions(parsedDocument){
    if(!suggestionsNode)return;
    const source=parsedDocument.getElementById("chat-suggestions");
    if(!source)return;
    const fragment=document.createDocumentFragment();
    source.querySelectorAll("[data-suggestion]").forEach(sourceButton=>{
      const button=document.createElement("button");
      button.type="button";
      button.className="suggestion";
      button.dataset.suggestion=sourceButton.dataset.suggestion||sourceButton.textContent;
      button.textContent=sourceButton.textContent;
      fragment.appendChild(button);
    });
    suggestionsNode.replaceChildren(fragment);
  }

  function markRead(){
    if(readPending)return;
    readPending=true;
    const data=new FormData();
    data.set("csrfmiddlewaretoken",csrf);
    data.set("action","read");
    fetch(window.location.href,{method:"POST",body:data,credentials:"same-origin",headers:{"X-CSRFToken":csrf,"X-Requested-With":"XMLHttpRequest"}})
      .then(response=>{
        if(!response.ok)throw new Error("read_failed");
        stream.dataset.unreadCount="0";
        if(unreadNode)unreadNode.textContent="0 unread";
      })
      .catch(()=>{})
      .finally(()=>{readPending=false;});
  }

  async function refresh(){
    try{
      const response=await fetch(`/discover/conversations/${id}/messages/?limit=60`,{headers:{Accept:"application/json"},credentials:"same-origin",cache:"no-store"});
      if(response.status===401||response.status===403){window.location.assign("/auth/login/?next="+encodeURIComponent(window.location.pathname));return;}
      const payload=await readApiPayload(response);
      if(!response.ok){setStatus(formatApiError(payload,response.status));return;}
      if(!payload){setStatus(formatApiError(null,response.status));return;}
      const messages=Array.isArray(payload.results)?payload.results.slice().reverse():Array.isArray(payload)?payload.slice().reverse():[];
      const wasFirstPayload=firstPayload;
      const newIncoming=!wasFirstPayload&&messages.some(message=>message.id&&!seenMessageIds.has(String(message.id))&&Number(message.sender_id)!==viewerId&&message.message_type!=="SYSTEM");
      messages.forEach(message=>{if(message.id)seenMessageIds.add(String(message.id));});
      const signature=JSON.stringify(messages.map(message=>[message.id,message.body,(message.attachments||[]).map(attachment=>[attachment.id,attachment.url,attachment.scan_status])]));
      if(signature!==lastSignature){render(messages);lastSignature=signature;}
      if(wasFirstPayload&&Number(stream.dataset.unreadCount||0)>0)markRead();
      else if(newIncoming)markRead();
      setStatus(role==="artisan"?"You can keep service updates and direct messages here.":"Messages are sent securely through the marketplace API.");
    }catch(_){setStatus(formatApiError(null,null,{networkError:true}));}
  }

  function clearAttachmentPreview(){
    if(!preview)return;
    preview.replaceChildren();
    preview.hidden=true;
  }

  function syncFileInput(){
    if(!fileInput||typeof DataTransfer==="undefined")return;
    try{
      const transfer=new DataTransfer();
      selectedFiles.forEach(file=>transfer.items.add(file));
      fileInput.files=transfer.files;
    }catch(_){
      // selectedFiles remains the source used to build the secure submission payload.
    }
  }

  function showAttachmentPreview(){
    if(!preview||!fileInput)return;
    clearAttachmentPreview();
    const files=selectedFiles.slice();
    if(!files.length)return;
    preview.hidden=false;
    const heading=document.createElement("p");
    heading.className="attachment-preview-heading";
    heading.textContent=`${files.length} attachment${files.length===1?"":"s"} ready to send`;
    preview.appendChild(heading);
    files.forEach((file,index)=>{
      const item=document.createElement("div");
      item.className="attachment-preview-item";
      if(file.type&&file.type.toLowerCase().startsWith("image/")&&window.FileReader){
        const image=document.createElement("img");
        image.alt=`Preview of ${file.name}`;
        image.loading="lazy";
        item.appendChild(image);
        const reader=new FileReader();
        reader.addEventListener("load",()=>{if(typeof reader.result==="string")image.src=reader.result;},{once:true});
        reader.readAsDataURL(file);
      }else{
        const icon=document.createElement("span");
        icon.className="attachment-file-mark";
        icon.setAttribute("aria-hidden","true");
        icon.textContent="↗";
        item.appendChild(icon);
      }
      const name=document.createElement("span");
      name.className="attachment-preview-name";
      name.textContent=file.name;
      item.appendChild(name);
      const remove=document.createElement("button");
      remove.type="button";
      remove.className="attachment-preview-remove";
      remove.dataset.attachmentIndex=String(index);
      remove.setAttribute("aria-label",`Remove ${file.name}`);
      remove.textContent="Remove";
      item.appendChild(remove);
      preview.appendChild(item);
    });
  }

  fileInput?.addEventListener("change",()=>{
    selectedFiles=Array.from(fileInput.files||[]);
    showAttachmentPreview();
  });
  preview?.addEventListener("click",event=>{
    const button=event.target.closest("[data-attachment-index]");
    if(!button)return;
    const index=Number(button.dataset.attachmentIndex);
    if(!Number.isInteger(index)||index<0||index>=selectedFiles.length)return;
    selectedFiles.splice(index,1);
    syncFileInput();
    showAttachmentPreview();
    setStatus(selectedFiles.length?"Attachment removed. The other files and message are unchanged.":"Attachment removed. Your message is unchanged.");
  });

  form?.addEventListener("submit",async event=>{
    event.preventDefault();
    if(sendingMessage)return;
    const body=input?.value.trim()||"";
    const files=selectedFiles.slice();
    if(!body&&!files.length){setStatus("Write a message or attach a photo or file first.");input?.focus();return;}
    if(files.length>5){setStatus("You can attach up to five files to one message.");fileInput?.focus();return;}
    const oversized=files.find(file=>file.size>10*1024*1024);
    if(oversized){setStatus(`${oversized.name} is over the 10 MB attachment limit.`);fileInput?.focus();return;}
    const data=new FormData(form);
    data.delete("attachments");
    files.forEach(file=>data.append("attachments",file,file.name));
    const sendButton=form.querySelector('button[type="submit"]');
    const controls=[input,fileInput,sendButton].filter(Boolean);
    const previousDisabled=controls.map(control=>control.disabled);
    sendingMessage=true;
    form.dataset.sending="true";
    controls.forEach(control=>{control.disabled=true;});
    setStatus(assistantEnabled?"Updating the request draft and sending securely…":"Sending securely…");
    try{
      const response=await fetch(window.location.href,{method:"POST",body:data,credentials:"same-origin",headers:{Accept:"text/html,application/json","X-Requested-With":"XMLHttpRequest","X-CSRFToken":csrf}});
      if(!response.ok){setStatus(formatApiError(await readApiPayload(response),response.status));return;}
      const html=await response.text();
      const parsed=new DOMParser().parseFromString(html,"text/html");
      const errorPanel=parsed.querySelector(".response-panel--error");
      if(errorPanel){
        const errorText=errorPanel.querySelector("p")?.textContent.trim()||"The message could not be sent.";
        setStatus(errorText);
        return;
      }
      if(response.url&&new URL(response.url).pathname!==window.location.pathname){window.location.assign(response.url);return;}
      updateAssistant(parsed);
      updateSuggestions(parsed);
      input.value="";
      if(fileInput)fileInput.value="";
      selectedFiles=[];
      clearAttachmentPreview();
      setStatus(assistantEnabled?"Sent securely. The request remains a draft until you review and submit it.":"Sent securely.");
      await refresh();
    }catch(_){setStatus(formatApiError(null,null,{networkError:true}));}
    finally{
      sendingMessage=false;
      delete form.dataset.sending;
      controls.forEach((control,index)=>{control.disabled=previousDisabled[index];});
    }
  });

  async function loop(){if(!document.hidden)await refresh();delay=Math.min(delay*1.2,12000);timer=window.setTimeout(loop,delay);}
  window.addEventListener("beforeunload",()=>window.clearTimeout(timer),{once:true});
  fileInput&&showAttachmentPreview();
  refresh();
  timer=window.setTimeout(loop,delay);

  document.querySelectorAll("form").forEach(moneyForm=>{
    const action=moneyForm.querySelector('input[name="action"]')?.value;
    if(action==="offer"||action==="counter"){
      moneyForm.addEventListener("submit",()=>{
        moneyForm.querySelectorAll('input[type="datetime-local"][name]').forEach(field=>{
          if(!field.value)return;
          const date=new Date(field.value);
          if(Number.isNaN(date.getTime()))return;
          const hidden=document.createElement("input");
          hidden.type="hidden";
          hidden.name=field.name;
          hidden.value=date.toISOString();
          moneyForm.appendChild(hidden);
          field.disabled=true;
        });
      });
    }
    const inputs=moneyForm.querySelectorAll("[data-money-input]");
    const total=moneyForm.querySelector("[data-money-total]");
    if(!inputs.length||!total)return;
    moneyForm.addEventListener("input",event=>{
      if(event.target===total){total.dataset.manual="true";return;}
      if(!event.target.matches("[data-money-input]")||total.dataset.manual==="true")return;
      const sum=Array.from(inputs).reduce((value,field)=>{
        const amount=Number(String(field.value||"").replace(/,/g,""));
        return value+(Number.isFinite(amount)?amount:0);
      },0);
      total.value=sum?sum.toFixed(2):"";
    });
  });
})();
