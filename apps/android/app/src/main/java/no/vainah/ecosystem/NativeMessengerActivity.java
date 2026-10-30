package no.vainah.ecosystem;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.view.animation.AlphaAnimation;
import android.view.animation.Animation;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Vainah Messenger's first real Android implementation.
 * No WebView, injected HTML or host configuration form. All primary UI
 * components are Android Views; message synchronization uses Vainah API.
 */
public final class NativeMessengerActivity extends Activity {
    private static final int BG = Color.rgb(9, 16, 30);
    private static final int PANEL = Color.rgb(18, 29, 49);
    private static final int PANEL2 = Color.rgb(27, 40, 62);
    private static final int TEXT = Color.rgb(245, 248, 255);
    private static final int MUTED = Color.rgb(152, 172, 201);
    private static final int BLUE = Color.rgb(34, 133, 248);
    private static final int LINE = Color.rgb(39, 52, 73);
    private NativeApi api;
    private LinearLayout root;
    private LinearLayout list;
    private FrameLayout contentFrame;
    private EditText search;
    private JSONArray chats = new JSONArray(), groups = new JSONArray(),
            channels = new JSONArray(), bots = new JSONArray();
    private JSONObject user = new JSONObject();
    private boolean verified = false, canManage = false;
    private String tab = "chats", query = "";
    private int generation = 0;
    private final Handler handler = new Handler(Looper.getMainLooper());

    private int dp(float n) { return (int) (getResources().getDisplayMetrics().density * n + .5f); }
    private LinearLayout.LayoutParams lp(int w, int h) { return new LinearLayout.LayoutParams(w < 0 ? w : dp(w), h < 0 ? h : dp(h)); }

    private GradientDrawable shape(int color, float radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(radius));
        return drawable;
    }
    private GradientDrawable border(int color, float radius) {
        GradientDrawable drawable = shape(color, radius);
        drawable.setStroke(dp(1), LINE);
        return drawable;
    }
    private TextView text(String label, int sp, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(label); view.setTextSize(sp); view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        view.setGravity(Gravity.CENTER_VERTICAL);
        return view;
    }
    private LinearLayout column() { LinearLayout row = new LinearLayout(this);row.setOrientation(1);return row; }
    private LinearLayout row() { LinearLayout row = new LinearLayout(this);row.setOrientation(0);row.setGravity(Gravity.CENTER_VERTICAL);return row; }
    private void pad(View v,int l,int t,int r,int b){v.setPadding(dp(l),dp(t),dp(r),dp(b));}
    private void space(LinearLayout parent,int height){View v=new View(this);parent.addView(v,lp(1,height));}
    private Button button(String label, boolean primary) {
        Button b = new Button(this);
        b.setAllCaps(false); b.setText(label); b.setTextSize(14);
        b.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        b.setTextColor(TEXT);b.setBackground(shape(primary?BLUE:PANEL2,14));
        b.setMinHeight(dp(48));b.setElevation(0);return b;
    }
    private EditText field(String hint, boolean password) {
        EditText e=new EditText(this);
        e.setTextColor(TEXT);e.setHintTextColor(MUTED);e.setTextSize(15);
        e.setSingleLine(true);e.setHint(hint);
        e.setInputType(password?(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD):
                (InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_CAP_SENTENCES));
        e.setBackground(border(PANEL2,14));pad(e,15,10,15,10);
        return e;
    }
    private void reset() {
        root.removeAllViews();root.setBackgroundColor(BG);
    }
    private void notice(String message) {
        Toast.makeText(this,message,Toast.LENGTH_LONG).show();
    }
    private void request(String method,String path,JSONObject payload,NativeApi.Callback callback) {
        if(api==null){notice("Нужен Vainah API. Добавьте VAINAH_BASE_URL в GitHub Variables и пересоберите приложение.");return;}
        api.call(method,path,payload,callback);
    }
    private JSONObject json(String... pairs) {
        JSONObject object = new JSONObject();
        for(int i=0;i+1<pairs.length;i+=2) {
            try {object.put(pairs[i],pairs[i+1]);}catch(Exception ignored){}
        }
        return object;
    }
    private String name(JSONObject obj) {return obj.optString("display_name",obj.optString("name","Vainah"));}

    @Override public void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        root=column();root.setBackgroundColor(BG);setContentView(root);
        String endpoint=BuildConfig.VAINAH_BASE_URL;
        if(endpoint.startsWith("https://") && !endpoint.contains("127.0.0.1") && !endpoint.contains("localhost"))
            api=new NativeApi(this,endpoint);
        showLogin();
        if(api!=null && api.hasSession()){
            request("GET","/api/auth/me",null,(data,error)->{
                if(error==null){user=data.optJSONObject("user");if(user==null)user=new JSONObject();showHome("chats");}
                else if(error.contains("API")||error.contains("подключ"))showNetworkError(error);
            });
        }
    }

    private void showLogin(){
        generation++;reset();
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);root.addView(scroll,lp(-1,-1));
        LinearLayout body=column();pad(body,25,58,25,30);scroll.addView(body);
        TextView mark=text("V",32,TEXT,true);mark.setGravity(Gravity.CENTER);
        mark.setBackground(shape(BLUE,23));body.addView(mark,lp(77,77));space(body,22);
        body.addView(text("Vainah Messenger",30,TEXT,true));space(body,8);
        body.addView(text("Ваши сообщения. Ваши правила.",15,MUTED,false));space(body,34);
        TextView top=text("Войти в Vainah",22,TEXT,true);body.addView(top);space(body,9);
        body.addView(text("Вход через Google или email. Без открытия сайта.",13,MUTED,false));space(body,22);
        Button google=button("Продолжить с Google",true);body.addView(google,lp(-1,54));space(body,18);
        TextView divider=text("ИЛИ ВОЙТИ ЧЕРЕЗ EMAIL",11,MUTED,true);divider.setGravity(Gravity.CENTER);
        body.addView(divider);space(body,18);
        EditText displayName=field("Ваше имя",false);displayName.setVisibility(View.GONE);
        body.addView(displayName,lp(-1,52));space(body,10);
        EditText email=field("Email",false);
        email.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        body.addView(email,lp(-1,52));space(body,10);
        EditText password=field("Пароль (от 10 символов)",true);body.addView(password,lp(-1,52));space(body,17);
        Button emailSubmit=button("Войти",false);body.addView(emailSubmit,lp(-1,50));space(body,14);
        Button switchMode=button("Создать Vainah ID",false);body.addView(switchMode,lp(-1,48));
        space(body,22);
        TextView error=text("",13,Color.rgb(255,171,179),false);body.addView(error);
        boolean[] signup={false};
        switchMode.setOnClickListener(v->{
            signup[0]=!signup[0];displayName.setVisibility(signup[0]?View.VISIBLE:View.GONE);
            top.setText(signup[0]?"Новый Vainah ID":"Войти в Vainah");
            emailSubmit.setText(signup[0]?"Зарегистрироваться":"Войти");
            switchMode.setText(signup[0]?"Уже есть аккаунт? Войти":"Создать Vainah ID");
            error.setText("");
        });
        emailSubmit.setOnClickListener(v->{
            String address=email.getText().toString().trim();
            String pass=password.getText().toString();
            if(!address.contains("@")||pass.length()<10){error.setText("Проверьте email и пароль (минимум 10 символов).");return;}
            String path=signup[0]?"/api/auth/register":"/api/auth/login";
            JSONObject payload=json("email",address,"password",pass);
            if(signup[0]){
                String display=displayName.getText().toString().trim();
                if(display.length()<2){error.setText("Введите имя (минимум 2 символа).");return;}
                try{payload.put("display_name",display);}catch(Exception ignored){}
            }
            emailSubmit.setEnabled(false);error.setText("Подключение к Vainah...");
            request("POST",path,payload,(data,failure)->{
                emailSubmit.setEnabled(true);
                if(failure!=null)error.setText(failure);
                else {user=data.optJSONObject("user");if(user==null)user=new JSONObject();showHome("chats");}
            });
        });
        google.setOnClickListener(v->{
            error.setText("");google.setEnabled(false);
            NativeGoogle.signIn(this,new NativeGoogle.Callback(){
                @Override public void onToken(String token){
                    request("POST","/api/auth/google",json("credential",token),(data,failure)->{
                        google.setEnabled(true);
                        if(failure!=null)error.setText(failure);
                        else{user=data.optJSONObject("user");if(user==null)user=new JSONObject();showHome("chats");}
                    });
                }
                @Override public void onError(String failure){google.setEnabled(true);error.setText(failure);}
            });
        });
        if(api==null) {
            error.setText("Сервер Vainah не задан в сборке. Для чатов нужен HTTPS API; сайт открывать не требуется.");
            emailSubmit.setEnabled(false);google.setEnabled(false);
        }
    }

    private void showNetworkError(String error){
        new AlertDialog.Builder(this).setTitle("Не удалось подключиться")
                .setMessage("Нативное приложение готово, но сервер сообщений не отвечает. "+error)
                .setPositiveButton("Повторить",(dialog,which)->{
                    request("GET","/api/auth/me",null,(result,issue)->{
                        if(issue==null){user=result.optJSONObject("user");showHome("chats");}
                        else notice(issue);
                    });
                }).setNegativeButton("Закрыть",null).show();
    }

    private void showHome(String target){
        tab=target;int epoch=++generation;reset();
        LinearLayout top=row();pad(top,20,15,13,8);root.addView(top,lp(-1,75));
        TextView heading=text(target.equals("chats")?"Vainah":target.equals("channels")?"Каналы":target.equals("bots")?"Боты":"Настройки",
                30,TEXT,true);
        top.addView(heading,new LinearLayout.LayoutParams(0,-1,1));
        if(target.equals("chats")){
            Button fresh=button("⌕",false);fresh.setTextSize(24);fresh.setBackground(shape(BG,12));
            top.addView(fresh,lp(45,46));fresh.setOnClickListener(v->{if(search!=null)search.requestFocus();});
            Button compose=button("✎",false);compose.setTextSize(22);compose.setBackground(shape(BG,12));
            top.addView(compose,lp(45,46));compose.setOnClickListener(v->newChat());
        }else{
            Button reload=button("⟳",false);reload.setBackground(shape(BG,12));top.addView(reload,lp(47,46));
            reload.setOnClickListener(v->showHome(target));
        }
        contentFrame=new FrameLayout(this);
        root.addView(contentFrame,new LinearLayout.LayoutParams(-1,0,1));
        ScrollView scroll=new ScrollView(this);
        scroll.setFillViewport(true);contentFrame.addView(scroll,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout container=column();scroll.addView(container);
        list=container;
        if(target.equals("chats")){
            search=field("Поиск чатов, контактов и каналов",false);
            search.setSingleLine(true);pad(search,18,7,18,7);
            LinearLayout.LayoutParams input=lp(-1,49);input.setMargins(dp(16),dp(4),dp(16),dp(8));
            container.addView(search,input);
            search.setText(query);
            search.addTextChangedListener(new TextWatcher(){
                public void beforeTextChanged(CharSequence s,int start,int count,int after){}
                public void onTextChanged(CharSequence s,int start,int before,int count){query=s.toString();renderChats();}
                public void afterTextChanged(Editable e){}
            });
            LinearLayout results=column();results.setTag("chatResults");container.addView(results,lp(-1,-2));
            Button floating=button("✎",true);floating.setTextSize(26);
            FrameLayout.LayoutParams floatParams=new FrameLayout.LayoutParams(dp(58),dp(58),Gravity.RIGHT|Gravity.BOTTOM);
            floatParams.setMargins(0,0,dp(19),dp(22));
            contentFrame.addView(floating,floatParams);floating.setOnClickListener(v->newChat());
            loadChats(epoch);
        }else if(target.equals("channels"))loadChannels(epoch);
        else if(target.equals("bots"))loadBots(epoch);
        else loadProfile(epoch);
        LinearLayout nav=row();pad(nav,7,4,7,5);nav.setBackground(border(PANEL,18));
        root.addView(nav,lp(-1,66));
        bottom(nav,"☏","Чаты","chats");
        bottom(nav,"◉","Каналы","channels");
        bottom(nav,"✦","Боты","bots");
        bottom(nav,"⚙","Настройки","settings");
    }

    private void bottom(LinearLayout bar,String glyph,String label,String destination) {
        LinearLayout cell=column();cell.setGravity(Gravity.CENTER);
        TextView icon=text(glyph,22,tab.equals(destination)?BLUE:MUTED,true);icon.setGravity(Gravity.CENTER);
        TextView title=text(label,11,tab.equals(destination)?BLUE:MUTED,tab.equals(destination));
        title.setGravity(Gravity.CENTER);cell.addView(icon,lp(-1,28));cell.addView(title,lp(-1,21));
        bar.addView(cell,new LinearLayout.LayoutParams(0,-1,1));
        cell.setOnClickListener(v->{if(!tab.equals(destination)){query="";showHome(destination);}});
    }

    private void loadChats(int epoch) {
        request("GET","/api/messenger/v2/chats",null,(d,e)->{
            if(epoch!=generation)return;
            if(e!=null){loadError(e);return;}chats=d.optJSONArray("items");if(chats==null)chats=new JSONArray();
            request("GET","/api/messenger/v2/groups",null,(g,ge)->{
                if(epoch!=generation)return;
                groups=ge==null?g.optJSONArray("items"):new JSONArray();if(groups==null)groups=new JSONArray();
                request("GET","/api/community/channels",null,(c,ce)->{
                    if(epoch!=generation)return;
                    channels=ce==null?c.optJSONArray("items"):new JSONArray();if(channels==null)channels=new JSONArray();
                    request("GET","/api/community/bots",null,(b,be)->{
                        if(epoch!=generation)return;
                        bots=be==null?b.optJSONArray("items"):new JSONArray();if(bots==null)bots=new JSONArray();
                        renderChats();
                    });
                });
            });
        });
    }

    private void loadError(String error) {
        list.removeAllViews();
        TextView text=text("Не удалось загрузить сообщения\n"+error,15,MUTED,false);
        pad(text,22,38,22,18);list.addView(text);
        Button retry=button("Повторить",true);LinearLayout.LayoutParams params=lp(-1,50);
        params.setMargins(dp(20),0,dp(20),0);list.addView(retry,params);
        retry.setOnClickListener(v->showHome(tab));
    }

    private String formatTime(long timestamp){
        if(timestamp<=0)return "";
        return new SimpleDateFormat("HH:mm",Locale.getDefault()).format(new Date(timestamp*1000));
    }

    private void renderChats() {
        if(!tab.equals("chats")||list==null)return;
        LinearLayout results=list.findViewWithTag("chatResults");
        if(results==null)return;results.removeAllViews();
        int count=0;String match=query.trim().toLowerCase(Locale.ROOT);
        for(int i=0;i<chats.length();i++){
            JSONObject c=chats.optJSONObject(i);if(c==null||c.optBoolean("archived"))continue;
            if(!name(c).toLowerCase(Locale.ROOT).contains(match) &&
               !c.optString("email").toLowerCase(Locale.ROOT).contains(match))continue;
            count++;final JSONObject chosen=c;
            addConversation(results,name(c),c.optString("preview",c.optString("email")),
                    c.optInt("unread"),formatTime(c.optLong("updated_at")),c.optBoolean("verified"),"direct",
                    ()->openThread(chosen,false));
        }
        for(int i=0;i<groups.length();i++){
            JSONObject c=groups.optJSONObject(i);if(c==null)continue;
            if(!name(c).toLowerCase(Locale.ROOT).contains(match))continue;
            count++;final JSONObject chosen=c;
            addConversation(results,name(c),c.optString("members","")+" участников",0,"",false,"group",
                    ()->openThread(chosen,true));
        }
        for(int i=0;i<channels.length();i++){
            JSONObject c=channels.optJSONObject(i);if(c==null||(!c.optBoolean("subscribed")&&!c.optBoolean("owner")))continue;
            if(!name(c).toLowerCase(Locale.ROOT).contains(match))continue;
            count++;final JSONObject chosen=c;
            addConversation(results,name(c),c.optString("description","Канал Vainah"),0,"",
                    c.optBoolean("verified"),"channel",()->openChannel(chosen));
        }
        for(int i=0;i<bots.length();i++){
            JSONObject c=bots.optJSONObject(i);if(c==null)continue;
            if(!name(c).toLowerCase(Locale.ROOT).contains(match))continue;
            count++;final JSONObject chosen=c;
            addConversation(results,name(c),c.optString("description","Бот Vainah"),0,"",false,"bot",
                    ()->openBot(chosen));
        }
        if(count==0){
            TextView empty=text(match.isEmpty()?"Пока нет переписок. Нажмите ✎, чтобы найти контакт.":"По вашему запросу ничего не найдено.",14,MUTED,false);
            empty.setGravity(Gravity.CENTER);pad(empty,25,76,25,25);results.addView(empty);
        }
    }

    private TextView avatar(String name,String type) {
        String letter=name.isEmpty()?"V":name.substring(0,1).toUpperCase(Locale.ROOT);
        if(type.equals("channel"))letter="◈";
        else if(type.equals("bot"))letter="✦";
        else if(type.equals("group"))letter="●";
        TextView circle=text(letter,22,TEXT,true);
        circle.setGravity(Gravity.CENTER);
        circle.setBackground(shape(type.equals("bot")?0xff176f76:type.equals("channel")?0xff2165c4:0xff576ab5,60));
        return circle;
    }
    private TextView badge(){
        TextView badge=text("✓",12,TEXT,true);badge.setGravity(Gravity.CENTER);
        badge.setBackground(shape(BLUE,30));
        if(android.animation.ValueAnimator.areAnimatorsEnabled()){
            Animation pulse=new AlphaAnimation(1f,.72f);
            pulse.setDuration(1450);pulse.setRepeatMode(Animation.REVERSE);
            pulse.setRepeatCount(Animation.INFINITE);badge.startAnimation(pulse);
        }
        return badge;
    }

    private void addConversation(LinearLayout container,String title,String preview,int unread,String when,
                                 boolean approved,String type,Runnable click){
        LinearLayout item=row();pad(item,17,14,16,14);
        TextView face=avatar(title,type);item.addView(face,lp(54,54));
        LinearLayout middle=column();pad(middle,12,0,5,0);
        LinearLayout heading=row();heading.addView(text(title,16,TEXT,true));
        if(approved){LinearLayout.LayoutParams b=lp(18,18);b.leftMargin=dp(6);heading.addView(badge(),b);}
        if(type.equals("bot")){TextView label=text("БОТ",10,MUTED,true);pad(label,8,2,8,2);heading.addView(label);}
        middle.addView(heading);
        TextView snippet=text(preview.isEmpty()?"Начните общение":preview,13,MUTED,false);
        snippet.setMaxLines(2);snippet.setEllipsize(android.text.TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams sn=lp(-1,-2);sn.topMargin=dp(4);middle.addView(snippet,sn);
        item.addView(middle,new LinearLayout.LayoutParams(0,-2,1));
        LinearLayout trailing=column();trailing.setGravity(Gravity.RIGHT|Gravity.TOP);
        TextView time=text(when,11,MUTED,false);time.setGravity(Gravity.RIGHT);trailing.addView(time);
        if(unread>0){space(trailing,8);TextView counter=text(String.valueOf(Math.min(unread,99)),12,TEXT,true);
            counter.setGravity(Gravity.CENTER);counter.setBackground(shape(BLUE,28));
            LinearLayout.LayoutParams cp=lp(25,25);cp.gravity=Gravity.RIGHT;trailing.addView(counter,cp);}
        item.addView(trailing,lp(40,-2));container.addView(item,lp(-1,-2));
        View divider=new View(this);divider.setBackgroundColor(LINE);
        LinearLayout.LayoutParams dl=lp(-1,1);dl.leftMargin=dp(83);container.addView(divider,dl);
        item.setOnClickListener(v->click.run());
    }

    private void newChat(){
        EditText email=field("Email пользователя Vainah ID",false);
        email.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        LinearLayout holder=column();pad(holder,20,12,20,4);holder.addView(email,lp(-1,52));
        new AlertDialog.Builder(this).setTitle("Новое сообщение").setView(holder)
                .setNegativeButton("Отмена",null).setPositiveButton("Найти",(d,w)->{
                    request("GET","/api/messenger/contact?email="+android.net.Uri.encode(
                            email.getText().toString().trim()),null,(result,error)->{
                        if(error!=null){notice(error);return;}
                        JSONObject contact=result.optJSONObject("contact");
                        if(contact!=null)openThread(contact,false);
                    });
                }).show();
    }

    private void showDetail(String title,boolean verified,String subtitle) {
        generation++;reset();
        LinearLayout header=row();pad(header,10,9,15,9);root.addView(header,lp(-1,65));
        Button back=button("‹",false);back.setTextSize(30);back.setBackground(shape(BG,10));
        header.addView(back,lp(48,47));back.setOnClickListener(v->showHome("chats"));
        TextView heading=text(title,19,TEXT,true);
        header.addView(heading,new LinearLayout.LayoutParams(0,-1,1));
        if(verified)header.addView(badge(),lp(19,19));
        if(!subtitle.isEmpty()){
            TextView sub=text(subtitle,11,MUTED,false);pad(sub,24,0,12,9);root.addView(sub,lp(-1,-2));
        }
    }

    private void openThread(JSONObject contact,boolean group){
        String id=contact.optString("id");
        showDetail(name(contact),contact.optBoolean("verified"),
                group?"Групповая переписка":"Личный чат · Vainah ID");
        FrameLayout messagesFrame=new FrameLayout(this);
        root.addView(messagesFrame,new LinearLayout.LayoutParams(-1,0,1));
        ScrollView scroll=new ScrollView(this);messagesFrame.addView(scroll,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout messages=column();pad(messages,14,15,14,15);scroll.addView(messages);
        LinearLayout composer=row();pad(composer,9,8,9,12);composer.setBackgroundColor(PANEL);root.addView(composer,lp(-1,76));
        EditText input=field("Сообщение",false);input.setSingleLine(false);input.setMaxLines(3);
        composer.addView(input,new LinearLayout.LayoutParams(0,dp(48),1));
        Button send=button("➤",true);send.setTextSize(22);LinearLayout.LayoutParams sp=lp(53,48);sp.leftMargin=dp(9);
        composer.addView(send,sp);
        Runnable refresh=()->{
            String path=group?"/api/messenger/v2/groups/"+id+"/messages":"/api/messenger/v2/thread/"+id;
            request("GET",path,null,(data,error)->{
                if(error!=null){notice(error);return;}
                messages.removeAllViews();
                JSONArray items=data.optJSONArray("items");if(items==null)return;
                for(int i=0;i<items.length();i++){
                    JSONObject message=items.optJSONObject(i);if(message==null)continue;
                    addBubble(messages,message.optString("body",""),message.optBoolean("mine"),
                            formatTime(message.optLong("created_at")),message.optBoolean("deleted"));
                }
                scroll.post(()->scroll.fullScroll(View.FOCUS_DOWN));
                if(!group)request("POST","/api/messenger/v2/thread/"+id+"/read",new JSONObject(),(ok,ignored)->{});
                else if(items.length()>0)request("POST","/api/messenger/v2/groups/"+id+"/read",new JSONObject(),(ok,ignored)->{});
            });
        };
        send.setOnClickListener(v->{
            String body=input.getText().toString().trim();if(body.isEmpty())return;
            send.setEnabled(false);
            JSONObject data=json("body",body);
            String path=group?"/api/messenger/v2/groups/"+id+"/send":"/api/messenger/v2/send";
            if(!group)try{data.put("contact_id",id);}catch(Exception ignored){}
            request("POST",path,data,(response,error)->{
                send.setEnabled(true);
                if(error!=null){notice(error);return;}
                input.setText("");refresh.run();
            });
        });
        refresh.run();
    }

    private void addBubble(LinearLayout panel,String body,boolean mine,String timestamp,boolean deleted){
        LinearLayout line=row();line.setGravity(mine?Gravity.RIGHT:Gravity.LEFT);
        TextView bubble=text(deleted?"Сообщение удалено":body,15,TEXT,false);
        pad(bubble,14,10,14,10);bubble.setMaxWidth(dp(300));
        bubble.setBackground(shape(mine?0xff3e5baf:PANEL2,16));
        LinearLayout.LayoutParams cell=lp(-2,-2);cell.setMargins(0,dp(5),0,dp(5));
        line.addView(bubble,cell);panel.addView(line,lp(-1,-2));
        if(!timestamp.isEmpty()){
            TextView label=text(timestamp,10,MUTED,false);label.setGravity(mine?Gravity.RIGHT:Gravity.LEFT);
            panel.addView(label,lp(-1,-2));
        }
    }

    private void loadChannels(int epoch){
        request("GET","/api/community/channels",null,(data,error)->{
            if(epoch!=generation)return;if(error!=null){loadError(error);return;}
            list.removeAllViews();channels=data.optJSONArray("items");if(channels==null)channels=new JSONArray();
            Button create=button("＋ Создать канал",true);
            LinearLayout.LayoutParams cp=lp(-1,48);cp.setMargins(dp(17),dp(9),dp(17),dp(13));list.addView(create,cp);
            create.setOnClickListener(v->createCommunity(true));
            for(int i=0;i<channels.length();i++){
                JSONObject channel=channels.optJSONObject(i);if(channel==null)continue;
                addConversation(list,name(channel),channel.optString("description","Канал"),
                        0,"",channel.optBoolean("verified"),"channel",()->openChannel(channel));
            }
        });
    }

    private void openChannel(JSONObject channel){
        String id=channel.optString("id");String label=name(channel);
        showDetail(label,channel.optBoolean("verified"),"Публикации канала");
        LinearLayout frame=column();root.addView(frame,new LinearLayout.LayoutParams(-1,0,1));
        ScrollView scroll=new ScrollView(this);frame.addView(scroll,lp(-1,-1));
        LinearLayout posts=column();pad(posts,17,16,17,25);scroll.addView(posts);
        if(!channel.optBoolean("owner")){
            Button join=button(channel.optBoolean("subscribed")?"Отписаться":"Подписаться",true);
            LinearLayout.LayoutParams jp=lp(-1,50);jp.setMargins(dp(17),dp(8),dp(17),dp(12));
            root.addView(join,jp);
            join.setOnClickListener(v->{
                boolean followed=channel.optBoolean("subscribed");
                request(followed?"DELETE":"POST","/api/community/channels/"+id+"/subscribe",null,(response,error)->{
                    if(error!=null){notice(error);return;}
                    try{channel.put("subscribed",!followed);}catch(Exception ignored){}
                    join.setText(followed?"Подписаться":"Отписаться");
                });
            });
        }else{
            Button publish=button("＋ Новая публикация",true);
            LinearLayout.LayoutParams pp=lp(-1,49);pp.setMargins(dp(17),dp(7),dp(17),dp(9));root.addView(publish,pp);
            publish.setOnClickListener(v->{
                EditText entry=field("Текст публикации",false);
                entry.setSingleLine(false);entry.setMinLines(3);
                new AlertDialog.Builder(this).setTitle("Публикация в "+label).setView(entry)
                        .setPositiveButton("Опубликовать",(dialog,which)->{
                            request("POST","/api/community/channels/"+id+"/posts",json("body",entry.getText().toString()),(obj,error)->{
                                if(error!=null)notice(error);else openChannel(channel);
                            });
                        }).setNegativeButton("Отмена",null).show();
            });
        }
        request("GET","/api/community/channels/"+id+"/posts",null,(data,error)->{
            if(error!=null){notice(error);return;}
            JSONArray items=data.optJSONArray("items");if(items==null)return;
            posts.removeAllViews();
            for(int i=0;i<items.length();i++){
                JSONObject post=items.optJSONObject(i);if(post==null)continue;
                addBubble(posts,post.optString("body"),false,formatTime(post.optLong("created_at")),false);
            }
            if(items.length()==0)posts.addView(text("Публикаций пока нет.",14,MUTED,false));
        });
    }

    private void loadBots(int epoch){
        request("GET","/api/community/bots",null,(data,error)->{
            if(epoch!=generation)return;if(error!=null){loadError(error);return;}
            list.removeAllViews();bots=data.optJSONArray("items");if(bots==null)bots=new JSONArray();
            Button create=button("＋ Создать бота",true);
            LinearLayout.LayoutParams cp=lp(-1,50);cp.setMargins(dp(17),dp(10),dp(17),dp(13));
            list.addView(create,cp);create.setOnClickListener(v->createCommunity(false));
            for(int i=0;i<bots.length();i++){
                JSONObject bot=bots.optJSONObject(i);if(bot==null)continue;
                addConversation(list,name(bot),bot.optString("description","Бот Vainah"),0,"",false,"bot",()->openBot(bot));
            }
        });
    }

    private void openBot(JSONObject bot){
        String id=bot.optString("id");
        showDetail(name(bot),false,"Автоматические ответы");
        ScrollView scroll=new ScrollView(this);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout content=column();pad(content,19,17,19,15);scroll.addView(content);
        content.addView(text("Спросить бота",19,TEXT,true));space(content,13);
        EditText question=field("Введите сообщение",false);content.addView(question,lp(-1,51));space(content,12);
        Button send=button("Отправить боту",true);content.addView(send,lp(-1,52));space(content,16);
        TextView answer=text("",15,MUTED,false);content.addView(answer);
        send.setOnClickListener(v->{
            request("POST","/api/community/bots/"+id+"/reply",json("message",question.getText().toString()),(data,error)->
                    answer.setText(error==null?data.optString("reply",""):error));
        });
        if(bot.optBoolean("owner")){
            space(content,35);content.addView(text("Настройка своего бота",19,TEXT,true));space(content,11);
            EditText trigger=field("Ключевое слово",false);content.addView(trigger,lp(-1,50));space(content,9);
            EditText response=field("Автоматический ответ",false);content.addView(response,lp(-1,52));space(content,11);
            Button save=button("Добавить правило",false);content.addView(save,lp(-1,50));
            save.setOnClickListener(v->request("POST","/api/community/bots/"+id+"/rules",
                    json("trigger",trigger.getText().toString(),"reply",response.getText().toString()),(d,e)->{
                        if(e!=null)notice(e);else{trigger.setText("");response.setText("");notice("Ответ сохранён");}
                    }));
        }
    }

    private void createCommunity(boolean channel){
        LinearLayout holder=column();pad(holder,22,7,22,10);
        EditText name=field(channel?"Название канала":"Название бота",false);
        EditText description=field("Описание",false);
        holder.addView(name,lp(-1,50));space(holder,10);holder.addView(description,lp(-1,50));
        new AlertDialog.Builder(this).setTitle(channel?"Новый канал":"Новый бот").setView(holder)
                .setPositiveButton("Создать",(dialog,which)->{
                    request("POST",channel?"/api/community/channels":"/api/community/bots",
                            json("name",name.getText().toString(),"description",description.getText().toString()),
                            (data,error)->{
                                if(error!=null)notice(error);
                                else showHome(channel?"channels":"bots");
                            });
                }).setNegativeButton("Отмена",null).show();
    }

    private void loadProfile(int epoch){
        list.removeAllViews();pad(list,20,18,20,20);
        list.addView(text(name(user),25,TEXT,true));space(list,7);
        list.addView(text(user.optString("email","Vainah ID"),14,MUTED,false));space(list,18);
        list.addView(text("Ваш Vainah ID",13,MUTED,false));space(list,7);
        TextView id=text(user.optString("id",""),12,TEXT,false);id.setTextIsSelectable(true);
        list.addView(id);space(list,22);
        request("GET","/api/messenger/v2/verification/me",null,(data,error)->{
            if(epoch!=generation)return;
            verified=error==null&&data.optBoolean("verified");
            canManage=error==null&&data.optBoolean("can_manage");
            if(verified){
                LinearLayout mark=row();mark.addView(text("Аккаунт подтверждён",15,TEXT,true));
                mark.addView(badge(),lp(20,20));list.addView(mark);
            }
            if(canManage){
                space(list,16);Button manage=button("Управление галочками Vainah",false);
                list.addView(manage,lp(-1,51));manage.setOnClickListener(v->manageBadge());
            }
        });
        Button link=button("Подключить вход Google",false);
        list.addView(link,lp(-1,51));space(list,13);
        link.setOnClickListener(v->NativeGoogle.signIn(this,new NativeGoogle.Callback(){
            public void onToken(String token){
                request("POST","/api/auth/google/link",json("credential",token),(d,e)->
                        notice(e!=null?e:"Google подключён к Vainah ID"));
            }
            public void onError(String error){notice(error);}
        }));
        Button logout=button("Выйти из аккаунта",false);list.addView(logout,lp(-1,51));
        logout.setOnClickListener(v->request("POST","/api/auth/logout",new JSONObject(),(d,e)->{
            if(api!=null)api.clear();user=new JSONObject();showLogin();
        }));
        space(list,18);
        list.addView(text("Переписки хранятся на сервере Vainah. Сквозного шифрования пока нет.",12,MUTED,false));
    }
    private void manageBadge(){
        EditText target=field("UUID пользователя",false);
        LinearLayout pane=column();pad(pane,20,9,20,7);pane.addView(target,lp(-1,51));
        new AlertDialog.Builder(this).setTitle("Подтвердить аккаунт").setView(pane)
                .setPositiveButton("Выдать галочку",(dialog,which)->changeBadge(target.getText().toString(),true))
                .setNeutralButton("Снять",(dialog,which)->changeBadge(target.getText().toString(),false))
                .setNegativeButton("Отмена",null).show();
    }
    private void changeBadge(String target,boolean approved){
        JSONObject value=json("user_id",target);try{value.put("verified",approved);}catch(Exception ignored){}
        request("POST","/api/messenger/v2/verification/manage",value,(d,e)->notice(e!=null?e:"Статус обновлён"));
    }
    @Override public void onBackPressed(){showHome("chats");}
    @Override protected void onDestroy(){generation++;if(api!=null)api.close();super.onDestroy();}
}
