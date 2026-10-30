package no.vainah.ecosystem;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.net.Uri;
import android.util.Base64;
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
import java.security.SecureRandom;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;

/**
 * Vainah Messenger's first real Android implementation.
 * No WebView, injected HTML or host configuration form. All primary UI
 * components are Android Views; message synchronization uses Vainah API.
 */
public final class NativeMessengerActivity extends Activity {
    private static final int BG = Color.rgb(13, 14, 17);
    private static final int PANEL = Color.rgb(29, 30, 34);
    private static final int PANEL2 = Color.rgb(39, 40, 44);
    private static final int TEXT = Color.rgb(249, 250, 252);
    private static final int MUTED = Color.rgb(146, 148, 155);
    private static final int BLUE = Color.rgb(34, 160, 246);
    private static final int LINE = Color.rgb(48, 49, 55);
    private NativeApi api;
    private LinearLayout root;
    private LinearLayout list;
    private FrameLayout contentFrame;
    private EditText search;
    private JSONArray chats = new JSONArray(), groups = new JSONArray(),
            channels = new JSONArray(), bots = new JSONArray();
    private JSONObject user = new JSONObject();
    private boolean verified = false, canManage = false;
    private String tab = "chats", query = "", chatFilter = "all";
    private boolean inDetail = false;
    private int generation = 0;
    private Runnable pendingPeopleSearch;
    private String pendingAppleState="", pendingAppleVerifier="";
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
        if(getIntent()!=null && getIntent().getData()!=null)handleAppleReturn(getIntent());
        if(api!=null && api.hasSession()){
            request("GET","/api/auth/me",null,(data,error)->{
                if(error==null){user=data.optJSONObject("user");if(user==null)user=new JSONObject();showHome("chats");}
                else if(error.contains("API")||error.contains("подключ"))showNetworkError(error);
            });
        }
    }

    private void showLogin(){
        inDetail = false;
        generation++;reset();
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);root.addView(scroll,lp(-1,-1));
        LinearLayout body=column();pad(body,25,58,25,30);scroll.addView(body);
        TextView mark=text("V",32,TEXT,true);mark.setGravity(Gravity.CENTER);
        mark.setBackground(shape(BLUE,23));body.addView(mark,lp(77,77));space(body,22);
        body.addView(text("Vainah Messenger",30,TEXT,true));space(body,8);
        body.addView(text("Ваши сообщения. Ваши правила.",15,MUTED,false));space(body,34);
        TextView top=text("Войти в Vainah",22,TEXT,true);body.addView(top);space(body,9);
        body.addView(text("Вход через Google или email. Без открытия сайта.",13,MUTED,false));space(body,22);
        Button google=button("Продолжить с Google",true);body.addView(google,lp(-1,54));space(body,10);
        Button apple=button("Продолжить с Apple ID",false);body.addView(apple,lp(-1,54));space(body,20);
        apple.setOnClickListener(v->beginAppleLogin());
        if(api!=null)request("GET","/api/auth/apple/config",null,(data,error)->{
            if(error==null && !data.optBoolean("enabled")){
                apple.setText("Apple ID · требуется настройка сервера");
            }
        });
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
            emailSubmit.setEnabled(false);google.setEnabled(false);apple.setEnabled(false);
        }
    }

    private void beginAppleLogin(){
        if(api==null){notice("Сервер Vainah не настроен");return;}
        byte[] random=new byte[32];new SecureRandom().nextBytes(random);
        pendingAppleVerifier=Base64.encodeToString(random,Base64.URL_SAFE|Base64.NO_WRAP|Base64.NO_PADDING);
        try {
            MessageDigest sha=MessageDigest.getInstance("SHA-256");
            String challenge=Base64.encodeToString(
                    sha.digest(pendingAppleVerifier.getBytes(StandardCharsets.UTF_8)),
                    Base64.URL_SAFE|Base64.NO_WRAP|Base64.NO_PADDING);
            request("POST","/api/auth/apple/start",json("challenge",challenge),(data,error)->{
                if(error!=null){pendingAppleVerifier="";notice(error);return;}
                String address=data.optString("url",""),state=data.optString("state","");
                Uri link=Uri.parse(address);
                if(!"https".equals(link.getScheme())||!"appleid.apple.com".equals(link.getHost())
                        ||state.length()<32){
                    pendingAppleVerifier="";notice("Некорректная ссылка на Apple ID");return;
                }
                pendingAppleState=state;
                try {
                    Intent browser=new Intent(Intent.ACTION_VIEW,link);
                    browser.addCategory(Intent.CATEGORY_BROWSABLE);
                    startActivity(browser);
                }catch(ActivityNotFoundException failure){notice("Не найден браузер для входа Apple");}
            });
        }catch(Exception failure){pendingAppleVerifier="";notice("Не удалось подготовить Apple ID");}
    }

    @Override protected void onNewIntent(Intent intent){
        super.onNewIntent(intent);setIntent(intent);handleAppleReturn(intent);
    }
    private void handleAppleReturn(Intent intent){
        Uri uri=intent==null?null:intent.getData();
        if(uri==null||!"vainah-messenger".equals(uri.getScheme())||
                !"auth".equals(uri.getHost())||!"/apple".equals(uri.getPath()))return;
        String state=uri.getQueryParameter("state");
        if(state==null||!state.equals(pendingAppleState)||pendingAppleVerifier.isEmpty()){
            notice("Срок входа Apple истёк. Начните вход ещё раз.");return;
        }
        String verifier=pendingAppleVerifier;
        pendingAppleVerifier="";pendingAppleState="";
        request("POST","/api/auth/apple/exchange",json("state",state,"verifier",verifier),(data,error)->{
            if(error!=null){notice(error);showLogin();return;}
            user=data.optJSONObject("user");
            if(user==null)user=new JSONObject();
            showHome("chats");
        });
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
        inDetail = false;
        tab=target;int epoch=++generation;reset();
        LinearLayout top=row();pad(top,20,15,13,8);root.addView(top,lp(-1,75));
        TextView heading=text(target.equals("chats")?"Vainah":target.equals("contacts")?"Контакты":
                target.equals("profile")?"Профиль":target.equals("channels")?"Каналы":
                target.equals("bots")?"Боты":"Настройки",28,TEXT,true);
        top.addView(heading,new LinearLayout.LayoutParams(0,-1,1));
        if(target.equals("chats")){
            Button fresh=button("⌕",false);fresh.setTextSize(24);fresh.setBackground(shape(BG,12));
            top.addView(fresh,lp(45,46));fresh.setOnClickListener(v->{if(search!=null)search.requestFocus();});
            Button compose=button("✎",false);compose.setTextSize(22);compose.setBackground(shape(BG,12));
            top.addView(compose,lp(45,46));compose.setOnClickListener(v->newConversation());
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
            search=field("⌕  Поиск чатов и @username",false);
            search.setSingleLine(true);pad(search,18,7,18,7);
            LinearLayout.LayoutParams input=lp(-1,49);input.setMargins(dp(16),dp(4),dp(16),dp(8));
            container.addView(search,input);
            search.setText(query);
            search.addTextChangedListener(new TextWatcher(){
                public void beforeTextChanged(CharSequence s,int start,int count,int after){}
                public void onTextChanged(CharSequence s,int start,int before,int count){
                    query=s.toString();renderChats();
                }
                public void afterTextChanged(Editable e){}
            });
            LinearLayout categories=row();pad(categories,5,4,5,4);
            categories.setBackground(shape(PANEL,23));
            LinearLayout.LayoutParams tabsParams=lp(-1,49);
            tabsParams.setMargins(dp(15),0,dp(15),dp(12));
            container.addView(categories,tabsParams);
            for(String[] option:new String[][]{{"Все","all"},{"Личные","direct"},{"Группы","group"},{"Каналы","channel"},{"Боты","bot"}}){
                String label=option[0],value=option[1];
                TextView chip=text(label,12,chatFilter.equals(value)?TEXT:MUTED,chatFilter.equals(value));
                chip.setGravity(Gravity.CENTER);
                if(chatFilter.equals(value))chip.setBackground(shape(0xff293d4b,18));
                categories.addView(chip,new LinearLayout.LayoutParams(0,-1,1));
                chip.setOnClickListener(v->{chatFilter=value;showHome("chats");});
            }
            LinearLayout results=column();results.setTag("chatResults");container.addView(results,lp(-1,-2));
            Button floating=button("✎",true);floating.setTextSize(26);
            FrameLayout.LayoutParams floatParams=new FrameLayout.LayoutParams(dp(58),dp(58),Gravity.RIGHT|Gravity.BOTTOM);
            floatParams.setMargins(0,0,dp(19),dp(22));
            contentFrame.addView(floating,floatParams);floating.setOnClickListener(v->newConversation());
            loadChats(epoch);
            handler.postDelayed(new Runnable(){
                @Override public void run(){
                    if(epoch!=generation||!tab.equals("chats")||isFinishing())return;
                    loadChats(epoch);
                    handler.postDelayed(this,15000);
                }
            },15000);
        }else if(target.equals("contacts"))loadContacts(epoch);
        else if(target.equals("channels"))loadChannels(epoch);
        else if(target.equals("bots"))loadBots(epoch);
        else if(target.equals("profile"))loadProfile(epoch);
        else loadSettings(epoch);
        LinearLayout nav=row();pad(nav,7,3,7,5);nav.setBackground(border(PANEL,25));
        LinearLayout.LayoutParams navSpace=lp(-1,68);
        navSpace.setMargins(dp(10),dp(4),dp(10),dp(9));
        root.addView(nav,navSpace);
        bottom(nav,"☏","Чаты","chats");
        bottom(nav,"◎","Контакты","contacts");
        bottom(nav,"⚙","Настройки","settings");
        bottom(nav,"●","Профиль","profile");
    }

    private void bottom(LinearLayout bar,String glyph,String label,String destination) {
        LinearLayout cell=column();cell.setGravity(Gravity.CENTER);
        if(tab.equals(destination))cell.setBackground(shape(0xff263846,23));
        TextView icon=text(glyph,23,tab.equals(destination)?BLUE:MUTED,true);icon.setGravity(Gravity.CENTER);
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
        LinearLayout target = tab.equals("chats") ? list.findViewWithTag("chatResults") : list;
        if (target == null) target = list;
        target.removeAllViews();
        TextView text=text("Не удалось загрузить сообщения\n"+error,15,MUTED,false);
        pad(text,22,38,22,18);target.addView(text);
        Button retry=button("Повторить",true);LinearLayout.LayoutParams params=lp(-1,50);
        params.setMargins(dp(20),0,dp(20),0);target.addView(retry,params);
        retry.setOnClickListener(v->showHome(tab));
    }

    private String formatTime(long timestamp){
        if(timestamp<=0)return "";
        long millis = timestamp > 100_000_000_000L ? timestamp : timestamp * 1000L;
        return new SimpleDateFormat("HH:mm",Locale.getDefault()).format(new Date(millis));
    }

    private void renderChats() {
        if(!tab.equals("chats")||list==null)return;
        LinearLayout results=list.findViewWithTag("chatResults");
        if(results==null)return;results.removeAllViews();
        int count=0;String match=query.trim().toLowerCase(Locale.ROOT);
        for(int i=0;i<chats.length();i++){
            JSONObject c=chats.optJSONObject(i);if(c==null||c.optBoolean("archived")||(!chatFilter.equals("all")&&!chatFilter.equals("direct")))continue;
            if(!name(c).toLowerCase(Locale.ROOT).contains(match) &&
               !c.optString("username").toLowerCase(Locale.ROOT).contains(match) &&
               !c.optString("email").toLowerCase(Locale.ROOT).contains(match))continue;
            count++;final JSONObject chosen=c;
            addConversation(results,name(c),c.optString("username").isEmpty() ?
                    c.optString("preview",c.optString("email")) :
                    "@"+c.optString("username")+" · "+c.optString("preview",""),
                    c.optInt("unread"),formatTime(c.optLong("updated_at")),c.optBoolean("verified"),"direct",
                    ()->openThread(chosen,false));
        }
        for(int i=0;i<groups.length();i++){
            JSONObject c=groups.optJSONObject(i);if(c==null||(!chatFilter.equals("all")&&!chatFilter.equals("group")))continue;
            if(!name(c).toLowerCase(Locale.ROOT).contains(match))continue;
            count++;final JSONObject chosen=c;
            addConversation(results,name(c),c.optString("preview",c.optInt("members")+" участников"),
                    c.optInt("unread"),formatTime(c.optLong("updated_at")),false,"group",
                    ()->openThread(chosen,true));
        }
        for(int i=0;i<channels.length();i++){
            JSONObject c=channels.optJSONObject(i);if(c==null||(!c.optBoolean("subscribed")&&!c.optBoolean("owner"))||(!chatFilter.equals("all")&&!chatFilter.equals("channel")))continue;
            if(!name(c).toLowerCase(Locale.ROOT).contains(match))continue;
            count++;final JSONObject chosen=c;
            addConversation(results,name(c),c.optString("description","Канал Vainah"),0,"",
                    c.optBoolean("verified"),"channel",()->openChannel(chosen));
        }
        for(int i=0;i<bots.length();i++){
            JSONObject c=bots.optJSONObject(i);if(c==null||(!chatFilter.equals("all")&&!chatFilter.equals("bot")))continue;
            if(!name(c).toLowerCase(Locale.ROOT).contains(match))continue;
            count++;final JSONObject chosen=c;
            addConversation(results,name(c),c.optString("description","Бот Vainah"),0,"",false,"bot",
                    ()->openBot(chosen));
        }
        if(count==0 && match.isEmpty()){
            TextView empty=text(chatFilter.equals("all")?"Пока нет переписок. Нажмите ✎, чтобы найти человека по @username.":"В этом разделе пока нет переписок.",14,MUTED,false);
            empty.setGravity(Gravity.CENTER);pad(empty,25,76,25,25);results.addView(empty);
        }
        if(pendingPeopleSearch!=null)handler.removeCallbacks(pendingPeopleSearch);
        String term=match.startsWith("@")?match.substring(1):match;
        if(term.length()>=3 && term.length()<=32 && term.matches("[a-z0-9_]+")){
            TextView label=text("ЛЮДИ ПО @USERNAME",12,MUTED,true);
            pad(label,19,22,16,10);results.addView(label);
            LinearLayout found=column();results.addView(found,lp(-1,-2));
            int epoch=generation;
            pendingPeopleSearch=()->request("GET","/api/people/search?q="+android.net.Uri.encode(term),null,(d,e)->{
                if(epoch!=generation || !term.equals(query.trim().toLowerCase(Locale.ROOT).replaceFirst("^@","")))return;
                found.removeAllViews();
                if(e!=null){found.addView(text("Поиск недоступен: "+e,13,MUTED,false));return;}
                JSONArray items=d.optJSONArray("items");
                if(items==null||items.length()==0){
                    TextView empty=text("Пользователи не найдены",13,MUTED,false);
                    pad(empty,20,12,10,12);found.addView(empty);return;
                }
                for(int i=0;i<items.length();i++){
                    JSONObject person=items.optJSONObject(i);if(person==null)continue;
                    addConversation(found,name(person),"@"+person.optString("username"),0,"",false,"direct",
                            ()->openThread(person,false));
                }
            });
            handler.postDelayed(pendingPeopleSearch,350);
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

    private void newConversation() {
        new AlertDialog.Builder(this).setTitle("Новая переписка")
                .setItems(new String[]{"Личное сообщение", "Создать группу"}, (dialog, which) -> {
                    if (which == 0) newChat();
                    else newGroup();
                }).setNegativeButton("Отмена", null).show();
    }

    private void newGroup() {
        LinearLayout holder=column();pad(holder,20,12,20,6);
        EditText title=field("Название группы",false);
        EditText participants=field("@username участников через запятую",false);
        participants.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        participants.setSingleLine(false);participants.setMinLines(2);participants.setMaxLines(4);
        holder.addView(title,lp(-1,52));space(holder,11);holder.addView(participants,lp(-1,-2));
        new AlertDialog.Builder(this).setTitle("Создать группу").setView(holder)
                .setPositiveButton("Создать",(dialog,which)->{
                    String label=title.getText().toString().trim();
                    if(label.length()<2||label.length()>80){notice("Название группы: от 2 до 80 символов.");return;}
                    String raw=participants.getText().toString();
                    java.util.LinkedHashSet<String> unique=new java.util.LinkedHashSet<>();
                    for(String part:raw.split("[,;\\n]+")){
                        String handle=part.trim().replaceFirst("^@","").toLowerCase(Locale.ROOT);
                        if(handle.isEmpty())continue;
                        if(!handle.matches("[a-z][a-z0-9_]{4,31}")){
                            notice("Неверный @username: "+handle);return;
                        }
                        unique.add(handle);
                    }
                    if(unique.size()>24){notice("В группе может быть не более 25 участников.");return;}
                    JSONObject payload=json("name",label);
                    try{payload.put("usernames",new JSONArray(unique));}catch(Exception ignored){}
                    request("POST","/api/messenger/v2/groups",payload,(result,error)->{
                        if(error!=null){notice(error);return;}
                        JSONObject group=new JSONObject();
                        try{
                            group.put("id",result.optString("id"));
                            group.put("name",result.optString("name",label));
                            group.put("owner_id",user.optString("id"));
                        }catch(Exception ignored){}
                        showHome("chats");
                        openThread(group,true);
                    });
                }).setNegativeButton("Отмена",null).show();
    }

    private void newChat(){
        EditText handle=field("@username или 10-значный Vainah ID",false);
        LinearLayout holder=column();pad(holder,20,12,20,4);holder.addView(handle,lp(-1,52));
        new AlertDialog.Builder(this).setTitle("Найти человека по @username").setView(holder)
                .setNegativeButton("Отмена",null).setPositiveButton("Искать",(d,w)->{
                    String term=handle.getText().toString().trim().replaceFirst("^@","").toLowerCase(Locale.ROOT);
                    if(term.matches("[0-9]{10}")){
                        request("GET","/api/people/id/"+term,null,(result,error)->{
                            if(error!=null){notice(error);return;}
                            JSONObject person=result.optJSONObject("person");
                            if(person!=null)openThread(person,false);
                        });
                        return;
                    }
                    if(term.length()<3 || !term.matches("[a-z0-9_]+")){notice("Введите @username или 10-значный ID");return;}
                    request("GET","/api/people/search?q="+android.net.Uri.encode(term),null,(result,error)->{
                        if(error!=null){notice(error);return;}
                        JSONArray people=result.optJSONArray("items");
                        if(people==null||people.length()==0){notice("Пользователи не найдены");return;}
                        String[] labels=new String[people.length()];
                        for(int i=0;i<people.length();i++){
                            JSONObject p=people.optJSONObject(i);
                            labels[i]=name(p)+"  @"+p.optString("username");
                        }
                        new AlertDialog.Builder(this).setTitle("Найденные люди")
                                .setItems(labels,(dialog,which)->{
                                    JSONObject person=people.optJSONObject(which);
                                    if(person!=null)openThread(person,false);
                                }).setNegativeButton("Закрыть",null).show();
                    });
                }).show();
    }
    private void promptUsernameInvite(String path,String title){
        EditText field=field("@username",false);
        LinearLayout holder=column();pad(holder,20,12,20,5);holder.addView(field,lp(-1,52));
        new AlertDialog.Builder(this).setTitle(title).setView(holder)
                .setNegativeButton("Отмена",null).setPositiveButton("Пригласить",(d,w)->{
                    String handle=field.getText().toString().trim().replaceFirst("^@","").toLowerCase(Locale.ROOT);
                    if(!handle.matches("[a-z][a-z0-9_]{4,31}")){notice("Проверьте @username");return;}
                    request("POST",path,json("username",handle),(result,error)->{
                        notice(error!=null?error:"Приглашение отправлено");
                    });
                }).show();
    }

    private void showDetail(String title,boolean verified,String subtitle) {
        inDetail = true;
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
        if(group && user.optString("id").equals(contact.optString("owner_id"))){
            Button addMember=button("＋ Добавить по @username",false);
            root.addView(addMember,lp(-1,49));
            addMember.setOnClickListener(v->promptUsernameInvite(
                    "/api/messenger/v2/groups/"+id+"/invite","Пригласить в группу"));
        }
        FrameLayout messagesFrame=new FrameLayout(this);
        root.addView(messagesFrame,new LinearLayout.LayoutParams(-1,0,1));
        ScrollView scroll=new ScrollView(this);messagesFrame.addView(scroll,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout messages=column();pad(messages,14,15,14,15);scroll.addView(messages);
        LinearLayout composer=row();pad(composer,9,8,9,12);composer.setBackgroundColor(PANEL);root.addView(composer,lp(-1,76));
        EditText input=field("Сообщение",false);input.setSingleLine(false);input.setMaxLines(3);
        composer.addView(input,new LinearLayout.LayoutParams(0,dp(48),1));
        Button send=button("➤",true);send.setTextSize(22);LinearLayout.LayoutParams sp=lp(53,48);sp.leftMargin=dp(9);
        composer.addView(send,sp);
        final int threadEpoch=generation;
        Runnable refresh=()->{
            if(threadEpoch!=generation)return;
            String path=group?"/api/messenger/v2/groups/"+id+"/messages":"/api/messenger/v2/thread/"+id;
            request("GET",path,null,(data,error)->{
                if(threadEpoch!=generation)return;
                if(error!=null){notice(error);return;}
                View child=scroll.getChildAt(0);
                boolean stickToBottom=child==null || messages.getChildCount()==0 ||
                        child.getHeight()-scroll.getScrollY()-scroll.getHeight()<dp(120);
                messages.removeAllViews();
                JSONArray items=data.optJSONArray("items");if(items==null)return;
                for(int i=0;i<items.length();i++){
                    JSONObject message=items.optJSONObject(i);if(message==null)continue;
                    String content=message.optString("body","");
                    if(group && !message.optBoolean("mine") && !message.optBoolean("deleted"))
                        content=message.optString("sender","Участник")+":\n"+content;
                    addBubble(messages,content,message.optBoolean("mine"),
                            formatTime(message.optLong("created_at")),message.optBoolean("deleted"));
                }
                if(stickToBottom)scroll.post(()->{
                    if(threadEpoch==generation)scroll.fullScroll(View.FOCUS_DOWN);
                });
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
                if(threadEpoch!=generation)return;
                send.setEnabled(true);
                if(error!=null){notice(error);return;}
                input.setText("");refresh.run();
            });
        });
        refresh.run();
        handler.postDelayed(new Runnable(){
            @Override public void run(){
                if(threadEpoch!=generation||isFinishing())return;
                refresh.run();
                handler.postDelayed(this,10000);
            }
        },10000);
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
            request("GET","/api/community/channels/invitations",null,(invitationData,inviteError)->{
                if(epoch!=generation || inviteError!=null)return;
                JSONArray invites=invitationData.optJSONArray("items");
                if(invites==null||invites.length()==0)return;
                TextView head=text("ПРИГЛАШЕНИЯ В КАНАЛЫ",12,MUTED,true);
                pad(head,20,12,12,11);list.addView(head);
                for(int i=0;i<invites.length();i++){
                    JSONObject invite=invites.optJSONObject(i);if(invite==null)continue;
                    LinearLayout entry=column();pad(entry,18,10,18,12);
                    entry.addView(text(invite.optString("channel_name")+" · от @"+invite.optString("invited_by"),14,TEXT,true));
                    space(entry,8);
                    LinearLayout actions=row();
                    Button accept=button("Принять",true),decline=button("Отклонить",false);
                    actions.addView(accept,new LinearLayout.LayoutParams(0,dp(43),1));
                    actions.addView(decline,new LinearLayout.LayoutParams(0,dp(43),1));
                    entry.addView(actions);list.addView(entry);
                    String inviteId=invite.optString("id");
                    accept.setOnClickListener(v->request("POST",
                            "/api/community/channels/invitations/"+inviteId+"/accept",new JSONObject(),
                            (res,err)->{if(err!=null)notice(err);else showHome("channels");}));
                    decline.setOnClickListener(v->request("DELETE",
                            "/api/community/channels/invitations/"+inviteId,null,
                            (res,err)->{if(err!=null)notice(err);else showHome("channels");}));
                }
            });
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
        if(channel.optBoolean("owner")){
            Button addPerson=button("＋ Пригласить по @username",false);
            root.addView(addPerson,lp(-1,48));
            addPerson.setOnClickListener(v->promptUsernameInvite(
                    "/api/community/channels/"+id+"/invite","Приглашение в канал"));
        }
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

    private void sectionLink(LinearLayout parent,String glyph,String title,String subtitle,Runnable action){
        LinearLayout item=row();pad(item,13,11,13,11);
        TextView icon=text(glyph,24,BLUE,true);icon.setGravity(Gravity.CENTER);
        icon.setBackground(shape(0xff263b49,13));item.addView(icon,lp(49,49));
        LinearLayout detail=column();pad(detail,14,0,0,0);
        detail.addView(text(title,17,TEXT,true));space(detail,3);
        detail.addView(text(subtitle,12,MUTED,false));
        item.addView(detail,new LinearLayout.LayoutParams(0,-2,1));
        TextView arrow=text("›",29,MUTED,false);item.addView(arrow);
        parent.addView(item,lp(-1,75));item.setOnClickListener(v->action.run());
    }

    private void loadSettings(int epoch){
        list.removeAllViews();pad(list,17,8,17,27);
        LinearLayout shortcuts=column();shortcuts.setBackground(shape(PANEL,24));
        list.addView(shortcuts,lp(-1,-2));
        sectionLink(shortcuts,"◉","Каналы","Мои каналы и подписки",()->showHome("channels"));
        sectionLink(shortcuts,"✦","Боты","Автоматические помощники",()->showHome("bots"));
        sectionLink(shortcuts,"◎","Контакты","Поиск людей по @username",()->showHome("contacts"));
        space(list,22);
        LinearLayout account=column();account.setBackground(shape(PANEL,24));
        list.addView(account,lp(-1,-2));
        sectionLink(account,"●","Аккаунт","Имя, @username и Vainah ID",()->showHome("profile"));
        sectionLink(account,"♧","Конфиденциальность","Сеансы и безопасность переписки",()->{
            new AlertDialog.Builder(this).setTitle("Конфиденциальность")
                .setMessage("Сессия хранится в зашифрованном хранилище Android. Сообщения синхронизируются с сервером Vainah. Сквозного шифрования пока нет.")
                .setPositiveButton("Понятно",null).show();
        });
        sectionLink(account,"◷","Уведомления","Push-уведомления ещё в разработке",()->{
            new AlertDialog.Builder(this).setTitle("Уведомления")
                .setMessage("В этой тестовой версии системные push-уведомления пока не подключены.")
                .setPositiveButton("Понятно",null).show();
        });
        space(list,18);
        list.addView(text("VAINAH MESSENGER  ·  0.9.4",12,MUTED,false));
    }

    private void loadContacts(int epoch){
        list.removeAllViews();pad(list,15,7,15,22);
        EditText input=field("⌕  Поиск по @username или Vainah ID",false);
        list.addView(input,lp(-1,52));space(list,13);
        LinearLayout results=column();results.setBackground(shape(PANEL,24));
        list.addView(results,lp(-1,-2));
        TextView hint=text("Найди человека по @username или точному 10-значному Vainah ID.",14,MUTED,false);
        pad(hint,17,28,17,29);results.addView(hint);
        input.addTextChangedListener(new TextWatcher(){
            public void beforeTextChanged(CharSequence value,int start,int count,int after){}
            public void onTextChanged(CharSequence value,int start,int before,int count){
                String term=value.toString().trim().toLowerCase(Locale.ROOT).replaceFirst("^@","");
                results.removeAllViews();
                if(pendingPeopleSearch!=null)handler.removeCallbacks(pendingPeopleSearch);
                boolean byId=term.matches("[0-9]{10}");
                if(!byId && term.length()<3){TextView empty=text("Введите @username или 10-значный ID",14,MUTED,false);
                    pad(empty,17,25,17,25);results.addView(empty);return;}
                if(!byId && !term.matches("[a-z0-9_]{3,32}"))return;
                String endpoint=byId?"/api/people/id/"+term:
                        "/api/people/search?q="+android.net.Uri.encode(term);
                pendingPeopleSearch=()->request("GET",endpoint,null,(data,error)->{
                    if(epoch!=generation||!input.getText().toString().trim().replaceFirst("^@","").equalsIgnoreCase(term))return;
                    results.removeAllViews();
                    if(error!=null){loadContactsError(results,error);return;}
                    if(byId){
                        JSONObject person=data.optJSONObject("person");
                        if(person==null){loadContactsError(results,"Пользователь не найден");return;}
                        String username=person.optString("username","");
                        addConversation(results,name(person),username.isEmpty()?
                                "Vainah ID: "+term:"@"+username+" · ID "+term,
                                0,"",false,"direct",()->openThread(person,false));
                    }else{
                        JSONArray matches=data.optJSONArray("items");
                        if(matches==null||matches.length()==0){
                            loadContactsError(results,"Никто не найден. Проверьте написание ника.");return;
                        }
                        for(int i=0;i<matches.length();i++){
                            JSONObject person=matches.optJSONObject(i);if(person==null)continue;
                            addConversation(results,name(person),"@"+person.optString("username"),0,"",false,"direct",
                                ()->openThread(person,false));
                        }
                    }
                });
                handler.postDelayed(pendingPeopleSearch,350);
            }
            public void afterTextChanged(Editable value){}
        });
        space(list,18);
        Button newChat=button("＋  Новое сообщение",true);
        list.addView(newChat,lp(-1,51));
        newChat.setOnClickListener(v->newChat());
    }

    private void loadContactsError(LinearLayout container,String message){
        TextView empty=text(message,14,MUTED,false);pad(empty,18,22,18,23);
        container.addView(empty);
    }

    private void loadProfile(int epoch){
        list.removeAllViews();pad(list,20,18,20,28);
        LinearLayout hero=column();hero.setGravity(Gravity.CENTER);
        TextView face=avatar(name(user),"direct");face.setTextSize(49);
        hero.addView(face,lp(114,114));space(hero,19);
        TextView display=text(name(user),28,TEXT,true);display.setGravity(Gravity.CENTER);
        hero.addView(display,lp(-1,43));space(hero,7);
        TextView emailLine=text(user.optString("email","Vainah ID"),14,MUTED,false);
        emailLine.setGravity(Gravity.CENTER);hero.addView(emailLine,lp(-1,27));space(hero,19);
        list.addView(hero,lp(-1,-2));
        Button editName=button("✎  Изменить имя",false);
        list.addView(editName,lp(-1,51));space(list,20);
        editName.setOnClickListener(v->{
            EditText input=field("Имя в Vainah",false);input.setText(name(user));
            LinearLayout holder=column();pad(holder,18,12,18,9);holder.addView(input,lp(-1,52));
            new AlertDialog.Builder(this).setTitle("Ваше имя").setView(holder)
                .setNegativeButton("Отмена",null).setPositiveButton("Сохранить",(d,w)->{
                    String value=input.getText().toString().trim();
                    if(value.length()<2||value.length()>80){notice("Имя должно быть от 2 до 80 символов");return;}
                    request("PATCH","/api/auth/profile",json("display_name",value),(data,error)->{
                        if(error!=null){notice(error);return;}
                        user=data.optJSONObject("user");if(user==null)user=new JSONObject();
                        showHome("profile");
                    });
                }).show();
        });
        LinearLayout identity=column();pad(identity,18,19,18,18);
        identity.setBackground(shape(PANEL,24));
        list.addView(identity,lp(-1,-2));
        identity.addView(text("ЛИЧНАЯ ИНФОРМАЦИЯ",12,BLUE,true));space(identity,12);
        TextView handleText=text("Публичный @username: не задан",16,BLUE,true);
        identity.addView(handleText);space(identity,12);
        identity.addView(text("VAINAH ID · ПОСТОЯННЫЙ",12,MUTED,true));space(identity,7);
        LinearLayout idRow=row();
        TextView numericId=text(user.optString("vainah_id","Загружается..."),23,TEXT,true);
        numericId.setTextIsSelectable(true);
        idRow.addView(numericId,new LinearLayout.LayoutParams(0,dp(48),1));
        Button copyId=button("Копировать",false);
        idRow.addView(copyId,lp(123,44));
        copyId.setOnClickListener(v->{
            String number=numericId.getText().toString();
            if(!number.matches("[0-9]{10}")){notice("Vainah ID ещё загружается");return;}
            ClipboardManager clipboard=(ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE);
            if(clipboard==null)return;
            clipboard.setPrimaryClip(ClipData.newPlainText("Vainah ID",number));
            notice("Vainah ID скопирован");
        });
        identity.addView(idRow);space(identity,15);
        request("GET","/api/people/me",null,(data,error)->{
            if(epoch!=generation)return;
            if(error==null){
                String value=data.optString("username","");
                if(!value.isEmpty()&&!value.equals("null"))handleText.setText("@"+value);
                String numeric=data.optString("vainah_id","");
                if(numeric.matches("[0-9]{10}"))numericId.setText(numeric);
            }
        });
        Button updateHandle=button("Установить или изменить @username",false);
        identity.addView(updateHandle,lp(-1,50));space(identity,18);
        updateHandle.setOnClickListener(v->{
            EditText field=field("Имя латиницей, от 5 до 32 символов",false);
            LinearLayout holder=column();pad(holder,20,10,20,8);holder.addView(field,lp(-1,52));
            new AlertDialog.Builder(this).setTitle("Публичное имя пользователя").setView(holder)
                .setNegativeButton("Отмена",null).setPositiveButton("Сохранить",(d,w)->{
                    String handle=field.getText().toString().trim().replaceFirst("^@","").toLowerCase(Locale.ROOT);
                    if(!handle.matches("[a-z][a-z0-9_]{4,31}")){notice("Имя: 5–32 символа, первая буква латинская");return;}
                    request("PUT","/api/people/username",json("username",handle),(response,error)->{
                        if(error!=null)notice(error);
                        else handleText.setText("@"+response.optString("username"));
                    });
                }).show();
        });
        identity.addView(text("ID не меняется при смене ника или входе с другого устройства.",12,MUTED,false));
        space(list,22);
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
    @Override public void onBackPressed(){
        if(!user.optString("id","").isEmpty() && inDetail){showHome(tab);return;}
        super.onBackPressed();
    }
    @Override protected void onDestroy(){generation++;handler.removeCallbacksAndMessages(null);if(api!=null)api.close();super.onDestroy();}
}
