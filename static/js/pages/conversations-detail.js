(function(){
  const apiErrors=window.ArtisanApiErrors;
  const formatApiError=(payload,status,options)=>apiErrors?apiErrors.format(payload,status,options):"The request could not be completed. Please try again.";
  const readApiPayload=(response)=>apiErrors?apiErrors.readResponse(response):response.json().catch(()=>null);

  /* ---------------------------------------------------------------------
     One poller for the whole page.

     Three things on this page used to watch the server: the message stream,
     the escrow strip and the bank-transfer card. Each ran its own timer, so an
     idle tab still made several calls every few seconds, and each of those
     calls could reach the payment provider. (The transfer card now polls on
     its own, shared with the payment page; this scheduler covers what is
     left.)

     This is the single scheduler they now share:

       * one in-flight request per endpoint, however many listeners subscribe;
       * it backs off while nothing changes instead of holding a fixed beat;
       * it sleeps while the tab is hidden and looks again the moment the tab
         comes back -- no request is ever made on a page nobody is reading;
       * it stops altogether once it is told to, and only a real action (a
         message sent, the tab focused, a tap in the chat) starts it again.
     --------------------------------------------------------------------- */
  const Poller=(()=>{
    const channels=new Map();
    const listeners=new WeakMap();
    const pageState={hidden:document.hidden};

    document.addEventListener("visibilitychange",()=>{
      pageState.hidden=document.hidden;
      if(document.hidden)return;
      channels.forEach(channel=>{
        if(channel.stopped)return;
        channel.backoff=0;
        schedule(channel,0);
      });
    });
    window.addEventListener("focus",()=>{
      if(document.hidden)return;
      channels.forEach(channel=>{
        if(channel.stopped)return;
        channel.backoff=0;
        schedule(channel,0);
      });
    });

    function schedule(channel,wait){
      window.clearTimeout(channel.timer);
      channel.timer=0;
      if(channel.stopped)return;
      const step=Math.min(
        channel.maxDelay,
        Math.max(channel.minDelay,channel.minDelay*Math.pow(1.6,channel.backoff||0))
      );
      channel.timer=window.setTimeout(run,typeof wait==="number"?wait:step,channel);
    }

    async function run(channel){
      channel.timer=0;
      if(channel.stopped)return;
      /* A hidden tab is a tab nobody is reading. Nothing is fetched until it
         is looked at again, which is what "stop calling until I do something"
         actually has to mean. */
      if(document.hidden){return;}
      if(channel.inFlight)return;
      channel.inFlight=true;
      try{
        const response=await fetch(channel.endpoint,{headers:{Accept:"application/json"},credentials:"same-origin",cache:"no-store"});
        if(response.status===401||response.status===403){channel.stopped=true;return;}
        if(response.ok){
          const data=await response.json().catch(()=>null);
          if(data){
            channel.backoff=0;
            (listeners.get(channel)||[]).forEach(handler=>{
              try{handler(data);}catch(_){/* one bad listener must not stop the poll */}
            });
            if(channel.done&&channel.done(data)){channel.stopped=true;return;}
          }
        }
      }catch(_){/* offline: the next tick tries again */}
      finally{
        channel.inFlight=false;
      }
      if(channel.stopped)return; /* the page is on its way out; nothing is applied and nothing is rescheduled */
      channel.backoff=(channel.backoff||0)+1;
      if(channel.budget&&channel.backoff>=channel.budget){channel.stopped=true;return;}
      schedule(channel);
    }

    return {
      /* Subscribe to an endpoint. Returns a handle with .kick() to poll now
         and .stop() to stop for good. */
      watch(endpoint,handler,{minDelay=6000,maxDelay=30000,budget=0,done=null}={}){
        if(!endpoint)return {kick(){},stop(){},restart(){}};
        let channel=channels.get(endpoint);
        if(!channel){
          channel={endpoint,minDelay,maxDelay,budget,done,timer:0,backoff:0,inFlight:false,stopped:false};
          channels.set(endpoint,channel);
          listeners.set(channel,[]);
        }else{
          channel.minDelay=Math.min(channel.minDelay,minDelay);
          channel.maxDelay=Math.max(channel.maxDelay,maxDelay);
          channel.budget=Math.max(channel.budget,budget||0);
          if(done)channel.done=channel.done||done;
        }
        const list=listeners.get(channel);
        list.push(handler);
        return {
          kick(){if(!channel.stopped)schedule(channel,0);},
          stop(){channel.stopped=true;window.clearTimeout(channel.timer);channel.timer=0;},
          restart(){channel.stopped=false;channel.backoff=0;schedule(channel,0);},
        };
      },
    };
  })();

  const stream=document.getElementById("conversation-stream");
  if(!stream)return;
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
  let delay=4000,timer=0,lastSignature="",firstPayload=true,readPending=false,sendingMessage=false;
  let selectedFiles=Array.from(fileInput?.files||[]);
  const seenMessageIds=new Set();
  const MEDIA_LIMIT_MB=30;
  const MEDIA_LIMIT_BYTES=MEDIA_LIMIT_MB*1024*1024;
  const VOICE_MAX_SECONDS=300;
  const MB=(bytes)=>`${Math.ceil(bytes/1024/1024)} MB`;
  let lastRenderedId=null,lastReadMessageId=null,lastOfferSignature=null;

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

  /* A missing file is answered once: the node swaps to a plain unavailable
     notice and nothing ever requests it again from this page. The server may
     still be scanning the upload or have purged it under the media policy --
     either way the room says so instead of hammering a 404. */
  function unavailableAttachment(label){
    const notice=document.createElement("span");
    notice.className="chat-attachment-unavailable";
    notice.textContent=`${label} unavailable — it may still be waiting to be checked, or it was removed under the media policy.`;
    return notice;
  }
  function watchMedia(node, label, host){
    node.addEventListener("error", () => {
      const replacement=unavailableAttachment(label);
      (host||node).replaceWith(replacement);
    }, {once:true});
    return node;
  }
  function makeAttachment(attachment){
    const url=safeUrl(attachment.url);
    if(!url){
      const type=String(attachment.content_type||'');
      if(type.match(/^image\//))return unavailableAttachment('Photo');
      if(type.match(/^(audio|video)\//))return unavailableAttachment('Recording');
      if(type.match(/^application\/pdf/))return unavailableAttachment('Document');
      return null;
    }
    if(String(attachment.content_type||'').match(/^(audio|video)\//)){
      const player=document.createElement(attachment.content_type.startsWith('audio/')?'audio':'video');
      player.controls=true;player.preload='none';player.src=url;player.playsInline=true;
      return watchMedia(player, attachment.content_type.startsWith('audio/')?'Audio':'Video', null);
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
      watchMedia(image, 'Photo', link);
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

  /* The little "Delete" affordance on your own messages. It asks first, then
     posts to the page action the server enforces -- the browser is never the
     only thing deciding who may remove a message. */
  function makeDeleteControl(messageId){
    if(!messageId)return document.createElement("span");
    const wrap=document.createElement("div");
    wrap.className="chat-message-tools";
    const trigger=document.createElement("button");
    trigger.type="button";
    trigger.className="chat-message-delete";
    trigger.setAttribute("aria-label","Delete this message");
    trigger.textContent="Delete";
    trigger.addEventListener("click",()=>{
      const confirmBtn=document.createElement("button");
      confirmBtn.type="button";
      confirmBtn.className="chat-message-delete is-confirming";
      confirmBtn.textContent="Delete for everyone?";
      confirmBtn.addEventListener("click",(event)=>{
        event.preventDefault();
        confirmBtn.disabled=true;
        confirmBtn.textContent="Deleting…";
        submitDelete(messageId).catch(()=>{
          confirmBtn.disabled=false;
          confirmBtn.textContent="Delete for everyone?";
          setStatus("That message could not be deleted. Try again.");
        });
      });
      trigger.replaceWith(confirmBtn);
      window.setTimeout(()=>{
        if(confirmBtn.isConnected&&!confirmBtn.disabled)confirmBtn.replaceWith(trigger);
      },5000);
    });
    wrap.appendChild(trigger);
    return wrap;
  }

  async function submitDelete(messageId){
    const data=new FormData();
    data.set("csrfmiddlewaretoken",csrf);
    data.set("action","delete_message");
    data.set("message_id",messageId);
    const response=await fetch(window.location.href,{
      method:"POST",
      body:data,
      credentials:"same-origin",
      headers:{"X-CSRFToken":csrf,"X-Requested-With":"XMLHttpRequest"},
    });
    if(!response.ok)throw new Error("delete_failed");
    await refresh();
    setStatus("Message deleted.");
  }

  /* Where the reader is, so a background rebuild never moves them: capture the
     first visible article before the stream is rebuilt and re-apply the same
     offset afterwards. */
  function firstVisibleAnchor(){
    const articles=Array.from(stream.querySelectorAll(":scope > article[data-message-id]"));
    if(!articles.length)return null;
    const areaRect=scrollArea.getBoundingClientRect();
    for(const article of articles){
      const rect=article.getBoundingClientRect();
      if(rect.bottom>areaRect.top+1){
        return {id:article.getAttribute("data-message-id"),delta:rect.top-areaRect.top};
      }
    }
    return null;
  }
  function restoreAnchor(anchor){
    if(!anchor)return;
    const renewed=stream.querySelector(`article[data-message-id="${CSS.escape(anchor.id)}"]`);
    if(!renewed)return;
    const areaRect=scrollArea.getBoundingClientRect();
    const rect=renewed.getBoundingClientRect();
    scrollArea.scrollTop+=rect.top-areaRect.top-anchor.delta;
  }
  function render(messages){
    const keepBottom=scrollArea.scrollHeight-scrollArea.scrollTop-scrollArea.clientHeight<120;
    const anchor=keepBottom?null:firstVisibleAnchor();
    const fragment=document.createDocumentFragment();
    messages.forEach(message=>{
      const article=document.createElement("article");
      const isMine=Number(message.sender_id)===viewerId;
      article.className="chat-message "+(message.message_type==="SYSTEM"?"system":isMine?"mine":"theirs");
      if(message.id)article.setAttribute("data-message-id",String(message.id));
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
      const gone=Boolean(message.deleted);
      bubble.className="chat-bubble"+(gone?" chat-bubble-deleted":"");
      const who=document.createElement("strong");
      who.textContent=message.message_type==="SYSTEM"?"Artisan Market":isMine?"You":(message.sender_name||"Participant");
      bubble.appendChild(who);
      if(gone){
        /* Deleted for everyone: the same plain line on both screens. The row
           itself stays on the server -- a marketplace chat is evidence once a
           booking is disputed -- so what is gone is the content, not the fact
           that something was said. */
        const tomb=document.createElement("p");
        tomb.className="chat-deleted-note";
        tomb.textContent="This message was deleted.";
        bubble.appendChild(tomb);
      }else if(message.body){
        const raw=String(message.body);
        const body=document.createElement("p");
        body.textContent=message.message_type==="SYSTEM"?raw.split("Next steps:")[0].trim():raw;
        bubble.appendChild(body);
      }
      /* Only your own chat message can be withdrawn, and a service update
         never can: that is the record of the job. */
      if(isMine&&!gone&&message.message_type!=="SYSTEM"){
        bubble.appendChild(makeDeleteControl(String(message.id||"")));
      }
      (message.attachments||[]).forEach(attachment=>{
        const rendered=makeAttachment(attachment);
        if(rendered)bubble.appendChild(rendered);
      });
      const time=document.createElement("time");
      time.dateTime=String(message.created_at||"");
      // Chat bubbles show the clock only, never a date: "12:34 pm".
      const parsedDate=new Date(message.created_at);
      time.textContent=Number.isNaN(parsedDate.getTime())
        ? String(message.created_at||"")
        : parsedDate.toLocaleTimeString([], {hour:"numeric", minute:"2-digit"}).toLowerCase().replace(/\s+/g," ");
      bubble.appendChild(time);
      article.appendChild(bubble);
      fragment.appendChild(article);
    });
    // Workflow cards live in the stream at their own event time. The poll
    // rebuilt the stream from the message payload alone, which would drop
    // them every few seconds; pick them up first and slot them back in
    // after the rebuild, oldest milestone first.
    const timelineCards=Array.from(stream.querySelectorAll(":scope > [data-timeline-card]"));
    if(!messages.length&&!timelineCards.length){
      const empty=document.createElement("div");
      empty.className="empty chat-empty-state";
      empty.textContent="No messages yet. Start the conversation naturally — you can write a note or attach a photo.";
      fragment.appendChild(empty);
    }
    stream.replaceChildren(fragment);
    reinsertTimelineCards(timelineCards);
    if(!firstPayload&&!keepBottom)restoreAnchor(anchor);
    if(firstPayload||keepBottom)pinToLatest(true);
    firstPayload=false;
    syncJumpButton();
    jumpRefresh();
  }

  /* Opening a conversation has to land on the newest message. A single
     scrollTop assignment happens before photos and attachments have a height,
     so the pane settles a little short of the bottom and the newest message
     looks missing -- the same complaint as "I cannot scroll to see below".
     So the bottom is re-asserted until the layout stops growing. */
  let pinTimer=0;
  function pinToLatest(immediate){
    const toBottom=()=>{scrollArea.scrollTop=scrollArea.scrollHeight;};
    toBottom();
    if(immediate!==true)return;
    window.clearTimeout(pinTimer);
    let rounds=0;
    const settle=()=>{
      const before=scrollArea.scrollHeight;
      toBottom();
      rounds+=1;
      if(rounds<12&&scrollArea.scrollHeight!==before)pinTimer=window.setTimeout(settle,120);
    };
    pinTimer=window.setTimeout(settle,60);
    requestAnimationFrame(toBottom);
  }
  /* Anything that loads late (a photo, a recording) changes the height under
     the pane: keep the bottom pinned while the reader is already at it. */
  stream.addEventListener("load",(event)=>{
    if(event.target&&event.target.tagName==="IMG"){
      if(scrollArea.scrollHeight-scrollArea.scrollTop-scrollArea.clientHeight<220)toLatestQuietly();
    }
  },true);
  function toLatestQuietly(){scrollArea.scrollTop=scrollArea.scrollHeight;}

  /* A pill that says there is more underneath, and takes you there: the plain
     answer to "no scroll" is a control that is obviously the way down. */
  const jump=document.createElement("button");
  jump.type="button";
  jump.className="chat-jump-latest";
  jump.hidden=true;
  jump.setAttribute("aria-label","Jump to the latest message");
  jump.innerHTML='<span aria-hidden="true">\u2193</span> Latest messages';
  jump.addEventListener("click",()=>{pinToLatest(false);syncJumpButton();});
  scrollArea.parentElement&&scrollArea.parentElement.appendChild(jump);
  function syncJumpButton(){
    const distance=scrollArea.scrollHeight-scrollArea.scrollTop-scrollArea.clientHeight;
    if(distance<240)unreadBelow=0;
    jumpRefresh();
  }
  scrollArea.addEventListener("scroll",()=>syncJumpButton(),{passive:true});

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

  /* The itemized offer is rendered by the server, so the card that greets the
     page and the card that a live quote produces are the same markup. When an
     offer event lands we re-read this page and swap only that node: the room
     stays where it is, a half-typed message survives, and there is no second
     copy of the card to drift out of step. */
  async function syncOfferCard(){
    try{
      const response=await fetch(window.location.pathname,{headers:{Accept:"text/html"},credentials:"same-origin",cache:"no-store"});
      if(!response.ok)return;
      const page=new DOMParser().parseFromString(await response.text(),"text/html");
      const fresh=page.getElementById("offer-card");
      const current=document.getElementById("offer-card");
      if(!fresh){current?.remove();return;}
      // Same offer, same version, same status: nothing to redraw.
      if(current&&fresh.dataset.offerEvent&&current.dataset.offerEvent===fresh.dataset.offerEvent)return;
      const node=document.importNode(fresh,true);
      if(current){current.replaceWith(node);}
      else{
        timelineInsert([node]);
      }
      node.classList.add("is-refreshed");
      window.setTimeout(()=>node.classList.remove("is-refreshed"),4000);
      if(scrollArea.scrollHeight-scrollArea.scrollTop-scrollArea.clientHeight<160)scrollArea.scrollTop=scrollArea.scrollHeight;
    }catch(_){/* the next poll tries again */}
  }

  async function refresh(){
    try{
      const response=await fetch(`/discover/conversations/${id}/messages/?limit=60`,{headers:{Accept:"application/json"},credentials:"same-origin",cache:"no-store"});
      if(response.status===401||response.status===403){window.location.assign("/auth/login/?next="+encodeURIComponent(window.location.pathname));return;}
      const payload=await readApiPayload(response);
      if(!response.ok){setStatus(formatApiError(payload,response.status));return;}
      if(!payload){setStatus(formatApiError(null,response.status));return;}
      applyMessages(payload);
    }catch(_){setStatus(formatApiError(null,null,{networkError:true}));}
  }

  /* Slot timeline cards (and the rebuilt messages) into strict chronological
     order. ISO timestamps compare as strings within one offset; normalise Z to
     +00:00 for safety. Untimed entries sink to the end, exactly like the
     server-side timeline. Ties break on the same fixed kind order the server
     uses, and the sort is stable, so same-instant entries keep their
     deterministic relative order. Nothing here depends on the order the
     requests completed in. */
  const normTimelineKey=value=>{const v=String(value||"").replace(/Z$/,"+00:00");return v?v:"\uffff";};
  const TIMELINE_KIND_ORDER={booking:0,dispute_case:1,offer:2,payment:3,addon:4,journey:5};
  const timelineKeyOf=node=>normTimelineKey(
    node.hasAttribute("data-timeline-card")
      ? node.getAttribute("data-sort-key")
      : node.getAttribute("data-message-created-at")
  );
  const timelineRankOf=node=>{
    if(!node.hasAttribute("data-timeline-card"))return 6;
    const kind=String(node.getAttribute("data-timeline-kind")||"");
    return Object.prototype.hasOwnProperty.call(TIMELINE_KIND_ORDER,kind)?TIMELINE_KIND_ORDER[kind]:5;
  };
  function timelineInsert(cards){
    (cards||[]).forEach(card=>stream.appendChild(card));
    const empty=stream.querySelector(":scope > .chat-empty-state");
    if(empty)empty.remove();
    const nodes=Array.from(stream.querySelectorAll(":scope > article[data-message-created-at], :scope > [data-timeline-card]"));
    nodes.sort((a,b)=>{
      const ka=timelineKeyOf(a),kb=timelineKeyOf(b);
      if(ka!==kb)return ka<kb?-1:1;
      return timelineRankOf(a)-timelineRankOf(b);
    });
    nodes.forEach(node=>stream.appendChild(node));
    if(empty)stream.appendChild(empty);
  }
  function reinsertTimelineCards(cards){
    // The card nodes were captured before the rebuild; appending them back
    // inside timelineInsert (then re-sorting the stream) reconciles API
    // payload order, WebSocket-adjacent delivery order and refresh order into
    // one deterministic chronological sequence.
    timelineInsert(cards);
  }

  /* The body of refresh(), split out so the shared poller can hand over the
     payload it already fetched: one request, not two, per beat. */
  function applyMessages(payload){
    try{
      let messages=Array.isArray(payload.results)?payload.results.slice().reverse():Array.isArray(payload)?payload.slice().reverse():[];
      // Any turn of the offer (sent, countered, accepted, declined, expired,
      // revision asked) means the card is stale: re-sync it in place.
      const offerSignature=messages
        .filter(message=>typeof message.event_code==="string"&&(message.event_code.startsWith("OFFER")||message.event_code==="QUOTE_REVISION_REQUESTED"))
        .map(message=>message.id)
        .join("|");
      const offersChanged=lastOfferSignature!==null&&offerSignature!==lastOfferSignature;
      lastOfferSignature=offerSignature;
      // Stable identity for de-duplication across every delivery path (API
      // poll, a pushed envelope, a refresh): the server-assigned event_key is
      // preferred; the message id is the fallback for plain user chat.
      const stableKey=message=>message&&message.event_key?`ek:${message.event_key}`:message&&message.id?`id:${message.id}`:null;
      // "Conversation started" is guidance and "Offer created/countered" is the
      // card itself. Both stay in the database for audit but never reappear as
      // a bare text bubble in the stream.
      messages=messages.filter(message=>message.event_code!=="CONVERSATION_STARTED"&&message.event_code!=="OFFER_CREATED"&&message.event_code!=="OFFER_COUNTERED");
      const wasFirstPayload=firstPayload;
      const unseenKey=message=>{const key=stableKey(message);return key&&!seenMessageIds.has(key);};
      const isCounterparty=message=>Number(message.sender_id)!==viewerId&&message.message_type!=="SYSTEM";
      const freshCount=!wasFirstPayload?messages.filter(message=>unseenKey(message)&&isCounterparty(message)).length:0;
      if(freshCount){
        if(scrollArea.scrollHeight-scrollArea.scrollTop-scrollArea.clientHeight>=240)unreadBelow+=freshCount;
      }
      messages.forEach(message=>{const key=stableKey(message);if(key)seenMessageIds.add(key);});
      const signature=JSON.stringify(messages.map(message=>[message.id,message.body,(message.attachments||[]).map(attachment=>[attachment.id,attachment.url,attachment.scan_status])]));
      if(signature!==lastSignature){render(messages);lastSignature=signature;}
      lastRenderedId=messages.length?String(messages[messages.length-1].id):null;
      markRead();
      if(offersChanged)syncOfferCard();
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
    syncComposerButtons();
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

  // WhatsApp-style composer: paperclip (photo / video / document), camera right
  // beside the mic, and the mic turning into Send as soon as there is anything
  // to send. No option sheet to read through.
  const sendButton=form?.querySelector('.chat-send-button');
  const attachButton=form?.querySelector('[data-composer-attach]');
  const cameraButton=form?.querySelector('[data-composer-camera]');
  const cameraInput=form?.querySelector('#conversation-camera');
  // One place decides what the right-hand button is: mic, stop, or Send.
  const syncComposerButtons=()=>{
    if(form&&typeof voiceState==='function')voiceState(form.dataset.voiceState||'idle');
  };
  // Files from the paperclip and from the camera share one queue.
  const queueFiles=incoming=>{
    const added=Array.from(incoming||[]);
    if(!added.length)return;
    selectedFiles=selectedFiles.concat(added);
    syncFileInput();
    showAttachmentPreview();
    syncComposerButtons();
  };
  attachButton?.addEventListener('click',()=>{
    if(!fileInput)return;
    fileInput.setAttribute('accept','image/*,video/*,audio/*,application/pdf');
    fileInput.click();
  });
  cameraButton?.addEventListener('click',()=>{
    if(cameraInput)cameraInput.click();
    else if(fileInput){fileInput.setAttribute('accept','image/*,video/*');fileInput.click();}
  });
  cameraInput?.addEventListener('change',()=>{
    queueFiles(cameraInput.files);
    cameraInput.value='';
  });
  input?.addEventListener('input',syncComposerButtons);

  // Voice notes. Tapping the mic starts recording visibly: the button becomes a
  // stop square, a live timer appears under the box, and Send stays hidden until
  // the recording has been stopped and staged.
  let voiceRecorder=null,voiceStream=null,voiceTimer=null,voiceBlobUrl=null,voiceFile=null,voiceRequesting=false,voiceLeaving=false;
  const voiceTools=form?.querySelector('[data-voice-tools]');
  const recordButton=form?.querySelector('[data-voice-record]');
  const discardButton=voiceTools?.querySelector('[data-voice-discard]');
  const voiceStatus=voiceTools?.querySelector('[data-voice-status]');
  const voiceDot=voiceTools?.querySelector('[data-voice-dot]');
  const voicePreview=voiceTools?.querySelector('[data-voice-preview]');
  const composerReady=()=>Boolean((input?.value||'').trim()||selectedFiles.length);
  function voiceState(state){
    if(!form)return;
    form.dataset.voiceState=state;
    if(recordButton){
      recordButton.hidden=!(state==='recording'||state==='starting'||!composerReady());
      recordButton.setAttribute('aria-pressed',String(state==='recording'));
      recordButton.setAttribute('aria-label',state==='recording'?'Stop recording':'Record an audio message');
      recordButton.disabled=state==='starting';
    }
    if(sendButton)sendButton.hidden=state==='recording'||state==='starting'||!composerReady();
    if(voiceTools)voiceTools.hidden=state==='idle';
    if(voiceDot)voiceDot.hidden=state!=='recording';
    if(discardButton)discardButton.hidden=state!=='ready';
    if(voicePreview)voicePreview.hidden=state!=='ready';
  }
  const voiceSay=text=>{if(voiceStatus)voiceStatus.textContent=text;};
  function releaseMicrophone(){clearInterval(voiceTimer);voiceStream?.getTracks().forEach(t=>t.stop());voiceStream=null;}
  function clearVoice(){
    if(voiceRecorder?.state==='recording')return;
    if(voiceBlobUrl)URL.revokeObjectURL(voiceBlobUrl);voiceBlobUrl=null;
    if(voiceFile)selectedFiles=selectedFiles.filter(f=>f!==voiceFile);voiceFile=null;
    if(voicePreview){voicePreview.pause();voicePreview.removeAttribute('src');}
    voiceSay('');
    voiceState('idle');
    syncFileInput();showAttachmentPreview();
  }
  discardButton?.addEventListener('click',()=>{clearVoice();syncComposerButtons();setStatus('Recording discarded.');});
  recordButton?.addEventListener('click',async()=>{
    if(sendingMessage)return;
    if(voiceRecorder?.state==='recording'){voiceRecorder.stop();return;}
    if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){
      voiceState('idle');
      if(voiceTools)voiceTools.hidden=false;
      voiceSay('This browser cannot record over this connection. Open the site on https, or attach an audio file with the paperclip.');
      setStatus('Recording needs https (or localhost). You can still attach an audio file.');
      return;
    }
    clearVoice();
    voiceState('starting');
    voiceSay('Asking for microphone permission…');
    voiceRequesting=true;
    try{
      voiceStream=await navigator.mediaDevices.getUserMedia({audio:true});
      voiceRequesting=false;
      if(voiceLeaving||sendingMessage){releaseMicrophone();voiceState('idle');return;}
      const mime=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(t=>window.MediaRecorder.isTypeSupported(t));
      if(!mime)throw Error('unsupported');
      const chunks=[];let bytes=0;const started=Date.now();
      voiceRecorder=new MediaRecorder(voiceStream,{mimeType:mime});
      voiceRecorder.ondataavailable=e=>{if(e.data.size){chunks.push(e.data);bytes+=e.data.size;if(bytes>MEDIA_LIMIT_BYTES&&voiceRecorder.state==='recording')voiceRecorder.stop();}};
      voiceRecorder.onstop=()=>{
        releaseMicrophone();
        if(bytes>MEDIA_LIMIT_BYTES){
          voiceState('idle');
          if(voiceTools)voiceTools.hidden=false;
          voiceSay(`That recording passed ${MEDIA_LIMIT_MB} MB. Record a shorter one.`);
          setStatus(`Recording exceeded ${MEDIA_LIMIT_MB} MB.`);
          return;
        }
        const seconds=Math.max(1,Math.round((Date.now()-started)/1000));
        const ext=mime.includes('mp4')?'m4a':mime.includes('ogg')?'ogg':'webm';
        voiceFile=new File(chunks,'voice-note.'+ext,{type:mime});
        selectedFiles.push(voiceFile);
        voiceBlobUrl=URL.createObjectURL(voiceFile);
        if(voicePreview)voicePreview.src=voiceBlobUrl;
        syncFileInput();showAttachmentPreview();
        voiceState('ready');
        voiceSay(`Voice note ready · ${seconds}s. Tap Send to send it, or discard.`);
      };
      voiceRecorder.onerror=()=>{
        releaseMicrophone();voiceRequesting=false;voiceState('idle');
        if(voiceTools)voiceTools.hidden=false;
        voiceSay('Recording failed. Try again, or attach an audio file.');
      };
      voiceRecorder.start(250);
      voiceState('recording');
      const clock=seconds=>`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;
      voiceTimer=setInterval(()=>{
        const seconds=Math.floor((Date.now()-started)/1000);
        voiceSay(`Recording ${clock(seconds)} · tap the button to stop`);
        if(seconds>=VOICE_MAX_SECONDS&&voiceRecorder.state==='recording')voiceRecorder.stop();
      },250);
    }catch(error){
      voiceRequesting=false;releaseMicrophone();voiceState('idle');
      if(voiceTools)voiceTools.hidden=false;
      const denied=error?.name==='NotAllowedError'||error?.name==='SecurityError';
      voiceSay(denied?'Microphone permission was blocked. Allow it in the browser, or attach an audio file.'
                     :'No microphone was available. Attach an audio file instead.');
      setStatus('Recording unavailable.');
    }
  });
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&voiceRecorder?.state==='recording')voiceRecorder.stop();});
  window.addEventListener('pagehide',()=>{voiceLeaving=true;if(voiceRecorder?.state==='recording'){voiceRecorder.onstop=null;voiceRecorder.stop();}releaseMicrophone();if(voiceBlobUrl)URL.revokeObjectURL(voiceBlobUrl);});

  form?.addEventListener("submit",async event=>{
    event.preventDefault();
    if(sendingMessage)return;
    if(voiceRequesting||voiceRecorder?.state==="recording"){setStatus("Stop the recording before sending.");return;}
    const body=input?.value.trim()||"";
    const files=selectedFiles.slice();
    if(!body&&!files.length){setStatus("Write a message or attach a photo or file first.");input?.focus();return;}
    if(files.length>5){setStatus("You can attach up to five files to one message.");fileInput?.focus();return;}
    const oversized=files.find(file=>file.size>MEDIA_LIMIT_BYTES);
    if(oversized){setStatus(`${oversized.name} is ${MB(oversized.size)}; the limit is ${MEDIA_LIMIT_MB} MB per file.`);fileInput?.focus();return;}
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

  /* The stream keeps itself current, but it does not keep calling forever: a
     quiet room is fetched a handful of times and then left alone until
     something actually happens -- this tab is looked at again, a key is
     pressed, the chat is clicked or a message is sent. An idle tab that
     refreshed every few seconds was doing nothing but burn requests. */
  const QUIET_POLLS_BEFORE_SLEEP=6;
  let quietPolls=0,asleep=true,lastSeenTopId="";
  const MESSAGE_POLL_DELAY=6000;
  /* The reader was away from the bottom when fresh content landed (a new
     message, or a poll that found the room changed): flag the jump pill so
     the new content is obvious without dragging them to it. */
  let unreadBelow=0;
  const jumpRefresh=()=>{
    const distance=scrollArea.scrollHeight-scrollArea.scrollTop-scrollArea.clientHeight;
    jump.hidden=distance<240;
    if(unreadBelow>0&&distance>=240){
      jump.innerHTML='<span aria-hidden="true">\u2193</span> '+unreadBelow+' new '+(unreadBelow===1?'message':'messages');
      jump.classList.add("chat-jump-latest--new");
    }else{
      jump.innerHTML='<span aria-hidden="true">\u2193</span> Latest messages';
      jump.classList.remove("chat-jump-latest--new");
    }
  };
  const messagePoller=Poller.watch(
    `/discover/conversations/${id}/messages/?limit=60`,
    /* The poller fetched this payload itself, so it is applied directly: the
       stream is never fetched twice for the same beat. */
    (payload)=>applyMessages(payload),
    {
      minDelay:MESSAGE_POLL_DELAY,
      maxDelay:20000,
      budget:QUIET_POLLS_BEFORE_SLEEP,
      /* Nothing new arrived: stop. Anything new (a message, an offer, an
         attachment finishing its scan) changes the signature, resets the
         budget and the room keeps itself up to date. */
      done:(payload)=>{
        const results=Array.isArray(payload&&payload.results)?payload.results:[];
        const newest=results.length?String(results[0].id||""):"";
        if(!newest)return false;
        if(newest!==lastSeenTopId){lastSeenTopId=newest;quietPolls=0;return false;}
        quietPolls+=1;
        return quietPolls>=QUIET_POLLS_BEFORE_SLEEP;
      },
    }
  );

  function wakeStream(){
    if(asleep){
      asleep=false;
      messagePoller.restart();
    }else{
      messagePoller.kick();
    }
  }
  /* A real action, not a clock: the tab comes back, the window is focused,
     the payer types or taps anything in this conversation. */
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)wakeStream();});
  window.addEventListener("focus",wakeStream);
  ["pointerdown","keydown","touchstart"].forEach(eventName=>{
    document.addEventListener(eventName,()=>{
      if(document.hidden)return;
      wakeStream();
    },{passive:true});
  });
  scrollArea.addEventListener("scroll",()=>{if(!document.hidden)wakeStream();},{passive:true});
  const stopStream=()=>messagePoller.stop();
  window.addEventListener("beforeunload",stopStream,{once:true});
  window.addEventListener("pagehide",stopStream,{once:true});
  window.addEventListener("pageshow",(event)=>{if(event.persisted)wakeStream();});
  fileInput&&showAttachmentPreview();
  syncComposerButtons();
  /* One fetch on load (refresh), then the poller takes over on its own beat --
     the room is not fetched twice for the same moment. */
  refresh();
  asleep=false;
  messagePoller.kick();
  /* Sending already refreshes; this makes sure the room is awake afterwards. */
  form&&form.addEventListener("submit",()=>window.setTimeout(wakeStream,0));

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
  const tools=document.getElementById("chat-service-tools");
  document.addEventListener("keydown",event=>{if(event.key==="Escape"&&tools?.open)tools.open=false;});

  /* Chat ⇄ Itemized offer. Switching tabs never touches the form, so a
     half-written quote and a half-typed message are both exactly where they
     were left; offer-draft.js also mirrors every keystroke to localStorage,
     so even a reload cannot lose the quote. */
  const modeToggle=document.querySelector("[data-chat-mode-toggle]");
  if(modeToggle){
    const tabs=Array.from(modeToggle.querySelectorAll("[data-chat-mode]"));
    const panes=Array.from(document.querySelectorAll("[data-chat-pane]"));
    const storeKey="artisan.chat-mode:"+(stream.dataset.conversationId||"");
    const setMode=(mode,focus)=>{
      tabs.forEach(tab=>{
        const active=tab.getAttribute("data-chat-mode")===mode;
        tab.classList.toggle("is-active",active);
        tab.setAttribute("aria-selected",active?"true":"false");
        if(active&&focus)tab.focus();
      });
      panes.forEach(pane=>{
        pane.classList.toggle("is-hidden",pane.getAttribute("data-chat-pane")!==mode);
      });
      try{window.sessionStorage.setItem(storeKey,mode);}catch(_){/* private mode: tab still works */}
    };
    tabs.forEach(tab=>{
      tab.addEventListener("click",()=>setMode(tab.getAttribute("data-chat-mode"),false));
      tab.addEventListener("keydown",event=>{
        if(event.key!=="ArrowLeft"&&event.key!=="ArrowRight")return;
        event.preventDefault();
        const index=tabs.indexOf(tab);
        const next=tabs[(index+(event.key==="ArrowRight"?1:tabs.length-1))%tabs.length];
        setMode(next.getAttribute("data-chat-mode"),true);
      });
    });
    // A failed offer send re-renders with the offer tab active (the server
    // decides); otherwise reopen on the tab this visitor last used.
    const offerPaneActive=!document.querySelector('[data-chat-pane="offer"].is-hidden');
    if(!offerPaneActive){
      let stored=null;
      try{stored=window.sessionStorage.getItem(storeKey);}catch(_){stored=null;}
      if(stored==="offer"&&modeToggle.querySelector('[data-chat-mode="offer"]'))setMode("offer",false);
    }
  }
})();

/* Escrow payment lives in the chat: while the provider link is being prepared,
   poll our own status route and swap the strip in place — no page hop. */
(() => {
  const strip = document.querySelector("[data-payment-watch]");
  if (!strip) return;
  const endpoint = strip.getAttribute("data-payment-watch");
  if (!endpoint) return;
  let waitedWithoutLink = false;
  /* One beat for this strip: it stretches while nothing changes, it sleeps
     while the tab is hidden, and it stops for good once the payment
     settles. The bank-transfer card keeps its own lazy poll (it also covers
     the payment page). It used to be a fixed 9-second call for as long as the
     page was open. */
  Poller.watch(
    endpoint,
    (data) => {
      const status = String(data.status || "").toUpperCase();
      const checkout = String(data.authorization_url || "");
      const button = strip.querySelector("[data-payment-pending-form] button");
      if (!checkout) {
        waitedWithoutLink = true;
      } else {
        const form = strip.querySelector("[data-payment-pending-form]");
        if (form && !strip.querySelector("[data-payment-checkout]")) {
          const link = document.createElement("a");
          link.className = "button button-primary button-small";
          link.href = checkout;
          link.setAttribute("data-artisan-action", "");
          link.setAttribute("data-payment-checkout", "");
          link.textContent = button ? button.textContent.trim() : "Continue secure payment";
          form.replaceWith(link);
        }
        // The payer tapped "Pay" and the link only arrived now: take them to
        // the provider instead of asking for a second tap. Only when this page
        // actually waited for it -- a chat opened with a link already in hand
        // must not navigate on its own, or paying and coming back would bounce
        // the payer straight back to Flutterwave.
        if (waitedWithoutLink) {
          window.location.assign(checkout);
          return;
        }
      }
      if (status && status !== "PAYMENT_PENDING") {
        window.location.reload();
      }
    },
    {
      minDelay: 7000,
      maxDelay: 45000,
      // Anything other than "still waiting" is the end of it: settle once and
      // stop calling, rather than polling a finished payment forever.
      done: (data) => {
        const status = String(data.status || "").toUpperCase();
        if (status && status !== "PAYMENT_PENDING") {
          window.location.reload();
          return true;
        }
        return false;
      },
    }
  );
})();
/* ---------------------------------------------------------------------------
   Quick schedule: one tap for the moments people actually mean.

   "Scheduled start" is a raw datetime-local input -- browser chrome that asks
   the artisan to type a date and a time by hand. These chips sit under it and
   fill in the usual answers ("tomorrow morning", "Saturday", "next week"), so
   the schedule is a tap for the common cases and the input stays there for the
   exact ones. Nothing is sent by choosing a chip; it only fills the field.
   --------------------------------------------------------------------------- */
(function () {
  const pad = (value) => String(value).padStart(2, "0");
  const toInputValue = (date) =>
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`;

  const nextWeekday = (from, weekday, hour) => {
    const date = new Date(from.getTime());
    let delta = (weekday - date.getDay() + 7) % 7;
    if (delta === 0) delta = 7;
    date.setDate(date.getDate() + delta);
    date.setHours(hour, 0, 0, 0);
    return date;
  };

  const buildOptions = (now) => {
    const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    const morning = new Date(tomorrow.getTime());
    morning.setHours(9, 0, 0, 0);
    const afternoon = new Date(tomorrow.getTime());
    afternoon.setHours(14, 0, 0, 0);
    return [
      { label: "Tomorrow 9am", date: morning },
      { label: "Tomorrow 2pm", date: afternoon },
      { label: "Saturday 10am", date: nextWeekday(now, 6, 10) },
      { label: "Monday 9am", date: nextWeekday(now, 1, 9) },
    ];
  };

  const decorate = (field) => {
    if (!field || field.dataset.scheduleQuick === "on") return;
    field.dataset.scheduleQuick = "on";
    const row = document.createElement("div");
    row.className = "schedule-quick";
    const label = document.createElement("span");
    label.className = "schedule-quick-label";
    label.textContent = "Or pick a time";
    row.appendChild(label);
    const buttons = [];
    buildOptions(new Date()).forEach((option) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.textContent = option.label;
      chip.setAttribute("aria-pressed", "false");
      chip.addEventListener("click", () => {
        field.value = toInputValue(option.date);
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.dispatchEvent(new Event("change", { bubbles: true }));
        buttons.forEach((other) =>
          other.setAttribute("aria-pressed", other === chip ? "true" : "false")
        );
      });
      buttons.push(chip);
      row.appendChild(chip);
    });
    field.parentElement && field.parentElement.appendChild(row);
  };

  const apply = () =>
    document
      .querySelectorAll('input[type="datetime-local"][name="scheduled_start"]')
      .forEach(decorate);

  apply();
  /* The offer panel is re-rendered in place, so watch for new fields. */
  const observer = new MutationObserver(apply);
  observer.observe(document.body, { childList: true, subtree: true });
})();
