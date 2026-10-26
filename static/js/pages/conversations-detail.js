(function(){
  const apiErrors=window.ArtisanApiErrors;
  const formatApiError=(payload,status,options)=>apiErrors?apiErrors.format(payload,status,options):"The request could not be completed. Please try again.";
  const readApiPayload=(response)=>apiErrors?apiErrors.readResponse(response):response.json().catch(()=>null);
  const stream=document.getElementById("conversation-stream");
  if(!stream)return;
  // Read-only guidance: changing a card never clicks/submits a transactional control.
  const guidanceNode=document.getElementById("booking-guidance");
  let guide=null,guideSignature="";
  function syncGuidance(next){
    if(!guidanceNode)return;
    const signature=JSON.stringify(next||null);
    if(signature===guideSignature)return;
    guideSignature=signature;guide=next;
    guidanceNode.hidden=!next;
    if(!next)return;
    for(const key of ["role","title","message"]){
      guidanceNode.querySelector(`[data-guide-${key}]`).textContent=next[key]||"";
    }
    const list=guidanceNode.querySelector("[data-guide-steps]");
    list.replaceChildren(...(next.steps||[]).map(text=>{const li=document.createElement("li");li.textContent=text;return li;}));
    const button=guidanceNode.querySelector("[data-guide-action]");
    button.hidden=!next.action;button.textContent=next.action?.label||"";
    guidanceNode.querySelector("[data-guide-status]").textContent="";
  }
  try{syncGuidance(JSON.parse(document.getElementById("booking-guidance-data")?.textContent||"null"));}catch(e){}
  guidanceNode?.querySelector("[data-guide-action]")?.addEventListener("click",()=>{
    const selectors={CONFIRM_DESCRIPTION:'.description-confirm-card, form:has(input[name="action"][value="description_done"])',EDIT_REQUEST:"#request-assistant-card, .request-card",SEND_OFFER:'.offer-create-card, form:has(input[name="action"][value="offer"])',REVISE_OFFER:'form:has(input[name="action"][value="offer"]), .offer-card',REVIEW_OFFER:'.offer-card, form:has(input[name="action"][value="accept"])',PAY:'form:has(input[name="action"][value="pay"])',START_BOOKING:'form:has(input[name="action"][value="start_booking"])',SUBMIT_COMPLETION:'form:has(input[name="action"][value="complete"])',CONFIRM_COMPLETION:'form:has(input[name="action"][value="confirm_completion"])',BOOKING:'.booking-card, a.workflow-text-link[href*="/bookings/"]',SUPPORT:'.support-case-card, .support-card'};
    const selector=selectors[guide?.action?.code];
    const target=selector?document.querySelector(selector):null;
    if(!target){guidanceNode.querySelector("[data-guide-status]").textContent="The next step has changed or its controls are not on this page. Refresh to load the current controls; use booking details or support if needed.";return;}
    let parent=target;
    while(parent){if(parent.tagName==="DETAILS")parent.open=true;parent=parent.parentElement;}
    const focus=target.matches("a,button,input,textarea,select")?target:target.querySelector('textarea:not([disabled]),input:not([type="hidden"]):not([disabled]),button:not([disabled]),summary,a');
    target.scrollIntoView({behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"center"});
    if(focus)focus.focus({preventScroll:true});
    guidanceNode.querySelector("[data-guide-status]").textContent="Review the existing controls below. Nothing has been submitted.";
  });
  const id=stream.dataset.conversationId;
  const form=document.getElementById("conversation-message-form");
  const input=form?.querySelector("textarea[name=body]");
  const fileInput=document.getElementById("conversation-attachments");
  const preview=document.getElementById("attachment-preview");
  const statusNode=document.getElementById("chat-status");
  const unreadNode=document.getElementById("chat-unread-count");
  const scrollArea=document.getElementById("conversation-scroll-area")||stream;
  const csrf=form?.querySelector("input[name=csrfmiddlewaretoken]")?.value||document.querySelector('meta[name="csrf-token"]')?.content||"";
  const viewerId=Number(stream.dataset.viewerId||0);
  const role=stream.dataset.role||"";
  let delay=4000,timer=0,lastSignature="",firstPayload=true,readPending=false,sendingMessage=false;
  let selectedFiles=Array.from(fileInput?.files||[]);
  const seenMessageIds=new Set();
  let lastRenderedId=null,lastReadMessageId=null;

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
  document.querySelectorAll('input[type="datetime-local"][data-utc-value]').forEach(field=>{
    const value=localDateTimeValue(field.dataset.utcValue||"");
    if(value)field.value=value;
  });
  document.querySelectorAll(".workflow-local-time[data-utc-time]").forEach(node=>{
    const date=new Date(node.dataset.utcTime||"");
    if(Number.isNaN(date.getTime()))return;
    node.textContent=date.toLocaleString(undefined,{weekday:"short",day:"numeric",month:"short",year:"numeric",hour:"numeric",minute:"2-digit"});
  });

  function makeAttachment(attachment){
    const url=safeUrl(attachment.url);
    if(!url){
      if(String(attachment.content_type||'').match(/^(audio|video)\//)){
        const notice=document.createElement('span');notice.textContent='Recording unavailable (scan pending or access closed under the media policy).';return notice;
      }
      return null;
    }
    if(String(attachment.content_type||'').match(/^(audio|video)\//)){
      const player=document.createElement(attachment.content_type.startsWith('audio/')?'audio':'video');
      player.controls=true;player.preload='none';player.src=url;player.playsInline=true;return player;
    }
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
    stream.replaceChildren(fragment);
    if(firstPayload||keepBottom)scrollArea.scrollTop=scrollArea.scrollHeight;
    firstPayload=false;
  }

  function markRead(){
    if(readPending||document.hidden||!lastRenderedId||lastRenderedId===lastReadMessageId)return;
    if(scrollArea.scrollHeight-scrollArea.scrollTop-scrollArea.clientHeight>80)return;
    const marker=lastRenderedId;
    readPending=true;
    const data=new FormData();
    data.set("csrfmiddlewaretoken",csrf);
    data.set("action","read");
    data.set("last_message_id",marker);
    fetch(window.location.href,{method:"POST",body:data,credentials:"same-origin",headers:{"X-CSRFToken":csrf,"X-Requested-With":"XMLHttpRequest"}})
      .then(response=>{
        if(!response.ok)throw new Error("read_failed");
        lastReadMessageId=marker;
        stream.dataset.unreadCount="0";
        if(unreadNode)unreadNode.textContent="0 unread";
      })
      .catch(()=>{})
      .finally(()=>{readPending=false;});
  }

  scrollArea.addEventListener("scroll",()=>markRead(),{passive:true});

  async function refresh(){
    try{
      const response=await fetch(`/discover/conversations/${id}/messages/?limit=60`,{headers:{Accept:"application/json"},credentials:"same-origin",cache:"no-store"});
      if(response.status===401||response.status===403){window.location.assign("/auth/login/?next="+encodeURIComponent(window.location.pathname));return;}
      const payload=await readApiPayload(response);
      if(!response.ok){setStatus(formatApiError(payload,response.status));return;}
      if(!payload){setStatus(formatApiError(null,response.status));return;}
      if(Object.prototype.hasOwnProperty.call(payload,"guidance"))syncGuidance(payload.guidance);
      const messages=Array.isArray(payload.results)?payload.results.slice().reverse():Array.isArray(payload)?payload.slice().reverse():[];
      const wasFirstPayload=firstPayload;
      const newIncoming=!wasFirstPayload&&messages.some(message=>message.id&&!seenMessageIds.has(String(message.id))&&Number(message.sender_id)!==viewerId&&message.message_type!=="SYSTEM");
      messages.forEach(message=>{if(message.id)seenMessageIds.add(String(message.id));});
      const signature=JSON.stringify(messages.map(message=>[message.id,message.body,(message.attachments||[]).map(attachment=>[attachment.id,attachment.url,attachment.scan_status])]));
      if(signature!==lastSignature){render(messages);lastSignature=signature;}
      lastRenderedId=messages.length?String(messages[messages.length-1].id):null;
      markRead();
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
    if(voiceFile&&!selectedFiles.includes(voiceFile))clearVoice();
    showAttachmentPreview();
  });
  preview?.addEventListener("click",event=>{
    const button=event.target.closest("[data-attachment-index]");
    if(!button)return;
    const index=Number(button.dataset.attachmentIndex);
    if(!Number.isInteger(index)||index<0||index>=selectedFiles.length)return;
    const removed=selectedFiles.splice(index,1)[0];
    if(removed===voiceFile)clearVoice();
    syncFileInput();
    showAttachmentPreview();
    setStatus(selectedFiles.length?"Attachment removed. The other files and message are unchanged.":"Attachment removed. Your message is unchanged.");
  });

  // MediaRecorder captures locally; nothing uploads until the normal Send action.
  let voiceRecorder=null,voiceStream=null,voiceTimer=null,voiceBlobUrl=null,voiceFile=null,voiceRequesting=false,voiceLeaving=false;
  const voiceTools=form?.querySelector('[data-voice-tools]');
  const recordButton=voiceTools?.querySelector('[data-voice-record]');
  const stopButton=voiceTools?.querySelector('[data-voice-stop]');
  const discardButton=voiceTools?.querySelector('[data-voice-discard]');
  const voiceStatus=voiceTools?.querySelector('[data-voice-status]');
  const voicePreview=voiceTools?.querySelector('[data-voice-preview]');
  function releaseMicrophone(){clearInterval(voiceTimer);voiceStream?.getTracks().forEach(t=>t.stop());voiceStream=null;}
  function clearVoice(){
    if(voiceRecorder?.state==='recording')return;
    if(voiceBlobUrl)URL.revokeObjectURL(voiceBlobUrl);voiceBlobUrl=null;
    if(voiceFile)selectedFiles=selectedFiles.filter(f=>f!==voiceFile);voiceFile=null;
    if(voicePreview){voicePreview.pause();voicePreview.removeAttribute('src');voicePreview.hidden=true;}
    if(discardButton)discardButton.hidden=true;
    if(recordButton)recordButton.disabled=false;
    if(voiceStatus)voiceStatus.textContent='Ready. Record or attach a supported file; nothing uploads until Send.';
    syncFileInput();showAttachmentPreview();
  }
  discardButton?.addEventListener('click',()=>{clearVoice();voiceStatus.textContent='Discarded. Record again or use the attachment control.';});
  stopButton?.addEventListener('click',()=>{if(voiceRecorder?.state==='recording')voiceRecorder.stop();});
  recordButton?.addEventListener('click',async()=>{
    if(sendingMessage)return;
    if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){voiceStatus.textContent='Recording unavailable. Use the attachment control or text.';return;}
    clearVoice();recordButton.disabled=true;voiceRequesting=true;
    try{
      voiceStream=await navigator.mediaDevices.getUserMedia({audio:true});voiceRequesting=false;
      if(voiceLeaving||sendingMessage){releaseMicrophone();recordButton.disabled=false;return;}
      const mime=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(t=>MediaRecorder.isTypeSupported(t));
      if(!mime)throw Error('unsupported');
      const chunks=[];let bytes=0;const started=Date.now();
      voiceRecorder=new MediaRecorder(voiceStream,{mimeType:mime});
      voiceRecorder.ondataavailable=e=>{if(e.data.size){chunks.push(e.data);bytes+=e.data.size;if(bytes>5*1024*1024&&voiceRecorder.state==='recording')voiceRecorder.stop();}};
      voiceRecorder.onstop=()=>{
        releaseMicrophone();stopButton.hidden=true;
        if(bytes>5*1024*1024){recordButton.disabled=false;voiceStatus.textContent='Recording exceeded 5 MB. Please re-record a shorter note.';return;}
        const ext=mime.includes('mp4')?'m4a':mime.includes('ogg')?'ogg':'webm';
        voiceFile=new File(chunks,'voice-note.'+ext,{type:mime});
        selectedFiles.push(voiceFile);syncFileInput();showAttachmentPreview();
        voiceBlobUrl=URL.createObjectURL(voiceFile);voicePreview.src=voiceBlobUrl;voicePreview.hidden=false;discardButton.hidden=false;
        voiceStatus.textContent='Preview your note. Use Send to upload, or Discard / re-record.';
      };
      voiceRecorder.onerror=()=>{releaseMicrophone();recordButton.disabled=false;stopButton.hidden=true;voiceStatus.textContent='Recording failed. Use file upload or text.';};
      voiceRecorder.start(250);stopButton.hidden=false;
      voiceTimer=setInterval(()=>{const seconds=Math.floor((Date.now()-started)/1000);voiceStatus.textContent='● Recording '+seconds+' / 90 seconds';if(Date.now()-started>=89500&&voiceRecorder.state==='recording')voiceRecorder.stop();},200);
    }catch(_){voiceRequesting=false;releaseMicrophone();recordButton.disabled=false;voiceStatus.textContent='Microphone denied or unavailable. Use the attachment control or text.';}
  });
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&voiceRecorder?.state==='recording')voiceRecorder.stop();});
  window.addEventListener('pagehide',()=>{voiceLeaving=true;if(voiceRecorder?.state==='recording'){voiceRecorder.onstop=null;voiceRecorder.stop();}releaseMicrophone();if(voiceBlobUrl)URL.revokeObjectURL(voiceBlobUrl);});

  form?.addEventListener("submit",async event=>{
    event.preventDefault();
    if(sendingMessage)return;
    if(voiceRequesting||voiceRecorder?.state==="recording"){setStatus("Stop and preview the recording before sending.");return;}
    const body=input?.value.trim()||"";
    const files=selectedFiles.slice();
    if(!body&&!files.length){setStatus("Write a message or attach a photo or file first.");input?.focus();return;}
    if(files.length>5){setStatus("You can attach up to five files to one message.");fileInput?.focus();return;}
    const oversized=files.find(file=>file.size>(file.type.startsWith("audio/")?5:10)*1024*1024);
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
    setStatus("Sending securely…");
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
      input.value="";
      if(fileInput)fileInput.value="";
      selectedFiles=[];
      clearVoice();
      clearAttachmentPreview();
      setStatus("Sent securely.");
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
