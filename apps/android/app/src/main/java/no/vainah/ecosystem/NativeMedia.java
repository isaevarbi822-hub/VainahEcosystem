package no.vainah.ecosystem;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ContentValues;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Outline;
import android.graphics.SurfaceTexture;
import android.media.MediaPlayer;
import android.media.MediaMetadataRetriever;
import android.util.LruCache;
import android.media.MediaRecorder;
import android.net.Uri;
import android.os.Build;
import android.os.SystemClock;
import android.provider.MediaStore;
import android.provider.OpenableColumns;
import android.view.Gravity;
import android.view.Surface;
import android.view.TextureView;
import android.view.View;
import android.view.ViewOutlineProvider;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.MediaController;
import android.widget.TextView;
import android.widget.Toast;
import android.widget.VideoView;

import androidx.core.content.FileProvider;

import org.json.JSONObject;

import java.io.File;
import java.util.UUID;

/**
 * Native Android media composer. Every photo/video/audio/doc uses authenticated
 * /send-file; capture files are private cache, never public URLs.
 * Video notes are short camera videos rendered inside a round-cropped player.
 */
public final class NativeMedia {
    public interface Listener {
        void onSent(String target, String error);
        void onRecording(boolean recording);
    }
    public static final int REQUEST_PICK = 8120;
    public static final int REQUEST_VIDEO_NOTE = 8121;
    public static final int REQUEST_MIC = 8122;
    private final Activity activity;
    private final NativeApi api;
    private final Listener listener;
    private String contactId = "";
    private boolean groupChat=false;
    private File captureFile;
    private String captureContact = "";
    private boolean captureGroup=false;
    private MediaRecorder recorder;
    private File voiceFile;
    private String voiceContact;
    private boolean voiceGroup=false;
    private long startedAt;
    private static final long MAX_FILE=20L * 1024 * 1024;
    // Recordings are private app files, not Android's evictable cache.
    private File pendingMediaDirectory(){
        File directory=new File(activity.getFilesDir(),"pending-media");
        if(!directory.exists() && !directory.mkdirs())
            throw new IllegalStateException("Unable to create private media directory");
        return directory;
    }
    // Small local cache for previews: never persist private attachments to shared storage.
    private final LruCache<String,Bitmap> thumbnails = new LruCache<String,Bitmap>(8*1024*1024){
        @Override protected int sizeOf(String key,Bitmap image){return image.getByteCount();}
    };

    public NativeMedia(Activity activity, NativeApi api, Listener listener) {
        this.activity=activity;
        this.api=api;
        this.listener=listener;
    }

    public void setContact(String target,boolean group) {
        contactId=target==null?"":target;groupChat=group;
    }
    public void clearContact(){contactId="";groupChat=false;}

    private void toast(String message){
        Toast.makeText(activity,message,Toast.LENGTH_LONG).show();
    }

    /** Show recordings surviving an app restart. Resend is explicit and only
     * targets the currently open conversation, never a guessed recipient. */
    public void showPendingRecordings(){
        if(contactId.isEmpty()){toast("Сначала откройте нужный чат");return;}
        File[] all=pendingMediaDirectory().listFiles();
        java.util.ArrayList<File> pending=new java.util.ArrayList<>();
        if(all!=null)for(File file:all){
            if(file.isFile() && file.length()>0 &&
                    (file.getName().endsWith(".m4a") || file.getName().endsWith(".mp4")))
                pending.add(file);
        }
        if(pending.isEmpty()){toast("Сохранённых записей нет");return;}
        pending.sort((a,b)->Long.compare(b.lastModified(),a.lastModified()));
        String[] labels=new String[pending.size()];
        for(int i=0;i<pending.size();i++){
            File file=pending.get(i);
            labels[i]=(file.getName().endsWith(".m4a")?"Голосовое":"Видео")
                    +" · "+(file.length()/1024)+" КБ · "
                    +new java.text.SimpleDateFormat("dd.MM HH:mm",java.util.Locale.getDefault())
                        .format(new java.util.Date(file.lastModified()));
        }
        new AlertDialog.Builder(activity).setTitle("Сохранённые записи")
                .setItems(labels,(dialog,index)->{
                    File selected=pending.get(index);
                    new AlertDialog.Builder(activity)
                            .setTitle("Сохранённая запись")
                            .setMessage("Отправить файл в открытый чат? Проверьте, не был ли он отправлен раньше.")
                            .setPositiveButton("Отправить",(d,w)->{
                                String mime=selected.getName().endsWith(".m4a")?"audio/mp4":"video/mp4";
                                Uri uri=FileProvider.getUriForFile(activity,
                                        activity.getPackageName()+".media",selected);
                                sendUri(contactId,groupChat,uri,selected.getName(),mime,selected);
                            })
                            .setNegativeButton("Удалить",(d,w)->{
                                if(!selected.delete())toast("Не удалось удалить запись");
                            })
                            .setNeutralButton("Отмена",null).show();
                }).setNegativeButton("Закрыть",null).show();
    }

    public void pickFile(){
        if(contactId.isEmpty()){toast("Откройте переписку");return;}
        Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT);
        picker.setType("*/*");
        picker.addCategory(Intent.CATEGORY_OPENABLE);
        picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        picker.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true);
        try{activity.startActivityForResult(picker,REQUEST_PICK);}
        catch(ActivityNotFoundException ex){toast("Системный выбор файлов недоступен");}
    }

    public void captureRoundVideo(){
        if(contactId.isEmpty()){toast("Откройте переписку");return;}
        try {
            captureFile=File.createTempFile("video-note-"+UUID.randomUUID()+"-",".mp4",pendingMediaDirectory());
            captureContact=contactId;
            captureGroup=groupChat;
            Uri output=FileProvider.getUriForFile(activity,
                    activity.getPackageName()+".media",captureFile);
            Intent camera=new Intent(MediaStore.ACTION_VIDEO_CAPTURE);
            camera.putExtra(MediaStore.EXTRA_DURATION_LIMIT,15);
            camera.putExtra(MediaStore.EXTRA_VIDEO_QUALITY,0);
            camera.putExtra(MediaStore.EXTRA_OUTPUT,output);
            camera.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            camera.setClipData(ClipData.newRawUri("Vainah video note",output));
            activity.startActivityForResult(camera,REQUEST_VIDEO_NOTE);
        }catch(Exception ex){toast("Не удалось открыть камеру для кружка");}
    }

    public void toggleVoice(){
        if(recorder!=null){stopVoice(true);return;}
        if(contactId.isEmpty()){toast("Откройте переписку");return;}
        if(Build.VERSION.SDK_INT>=23 &&
                activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){
            activity.requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},REQUEST_MIC);
            return;
        }
        startVoice();
    }

    public void permissionResult(int code,int[] grants){
        if(code==REQUEST_MIC){
            if(grants.length>0 && grants[0]==PackageManager.PERMISSION_GRANTED)startVoice();
            else toast("Для голосовых сообщений нужен доступ к микрофону");
        }
    }

    private void startVoice(){
        try {
            voiceContact=contactId;
            voiceGroup=groupChat;
            voiceFile=File.createTempFile("voice-"+UUID.randomUUID()+"-",".m4a",pendingMediaDirectory());
            recorder=new MediaRecorder();
            recorder.setAudioSource(MediaRecorder.AudioSource.MIC);
            recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
            recorder.setAudioEncodingBitRate(64000);
            recorder.setAudioSamplingRate(44100);
            recorder.setOutputFile(voiceFile.getAbsolutePath());
            recorder.prepare();
            recorder.start();
            startedAt=SystemClock.elapsedRealtime();
            listener.onRecording(true);
        }catch(Exception ex){
            releaseRecorder();
            if(voiceFile!=null)voiceFile.delete();
            voiceFile=null;
            toast("Не удалось начать запись голоса");
            listener.onRecording(false);
        }
    }

    public void stopVoice(boolean send){
        if(recorder==null)return;
        boolean valid=true;
        try{recorder.stop();}catch(RuntimeException ex){valid=false;}
        releaseRecorder();
        listener.onRecording(false);
        if(!valid || !send || voiceFile==null || voiceFile.length()<1000 ||
                SystemClock.elapsedRealtime()-startedAt<650){
            if(voiceFile!=null)voiceFile.delete();
            if(send)toast("Запись слишком короткая. Попробуйте ещё раз.");
            voiceFile=null;
            return;
        }
        File finished=voiceFile;
        voiceFile=null;
        String target=voiceContact;
        try {
            Uri uri=FileProvider.getUriForFile(activity,activity.getPackageName()+".media",finished);
            sendUri(target,voiceGroup,uri,finished.getName(),"audio/mp4",finished);
        }catch(RuntimeException ex){
            finished.delete();
            toast("Не удалось подготовить голосовое сообщение");
        }
    }

    private void releaseRecorder(){
        MediaRecorder active=recorder;
        recorder=null;
        if(active!=null){
            try{active.reset();}catch(RuntimeException ignored){}
            try{active.release();}catch(RuntimeException ignored){}
        }
    }

    public void cancelRecording(){stopVoice(false);}

    private String displayName(Uri uri){
        try(Cursor cursor=activity.getContentResolver().query(uri,
                new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){
            if(cursor!=null && cursor.moveToFirst())return cursor.getString(0);
        }catch(Exception ignored){}
        return "media-"+UUID.randomUUID();
    }

    private void sendUri(String target,boolean group,Uri uri,String filename,String mime,File temp){
        sendUriWithId(target,group,uri,filename,mime,temp,UUID.randomUUID().toString());
    }

    private void sendUriWithId(String target,boolean group,Uri uri,String filename,String mime,
                               File temp,String uploadId){
        if(target==null || target.isEmpty()){if(temp!=null)temp.delete();return;}
        api.uploadAttachment(target,group,uri,filename,mime,uploadId,(response,error)->{
            if(error==null){
                if(temp!=null)temp.delete();
                listener.onSent(target,null);
            }else{
                // A failed upload must not silently discard the original recording.
                // Keep the cache file for this session and offer a manual retry.
                listener.onSent(target,error);
                if(temp!=null && temp.exists()){
                    new AlertDialog.Builder(activity)
                            .setTitle("Не удалось отправить медиа")
                            .setMessage("Запись сохранена в приложении. Повторить отправку?")
                            .setPositiveButton("Повторить",(dialog,which)->
                                    sendUriWithId(target,group,uri,filename,mime,temp,uploadId))
                            .setNeutralButton("Закрыть",(dialog,which)->
                                    toast("Запись осталась в приватном хранилище, но автоматическое восстановление ещё не реализовано"))
                            .setNegativeButton("Удалить",(dialog,which)->temp.delete())
                            .show();
                }
            }
        });
    }

    public void activityResult(int requestCode,int resultCode,Intent data){
        if(requestCode==REQUEST_VIDEO_NOTE){
            File output=captureFile;
            String target=captureContact;
            boolean group=captureGroup;
            captureFile=null;captureContact="";captureGroup=false;
            if(resultCode!=Activity.RESULT_OK){
                if(output!=null)output.delete();
                return;
            }
            if(output!=null && output.length()>1500){
                Uri uri=FileProvider.getUriForFile(activity,
                        activity.getPackageName()+".media",output);
                sendUri(target,group,uri,output.getName(),"video/mp4",output);
            }else {
                if(output!=null)output.delete();
                Uri uri=data!=null?data.getData():null;
                if(uri!=null)sendUri(target,group,uri,"video-note-"+UUID.randomUUID()+".mp4","video/mp4",null);
                else toast("Камера не сохранила видеокружок");
            }
        }else if(requestCode==REQUEST_PICK && resultCode==Activity.RESULT_OK && data!=null){
            String target=contactId;
            boolean group=groupChat;
            java.util.ArrayList<Uri> chosen=new java.util.ArrayList<>();
            if(data.getClipData()!=null){
                ClipData clip=data.getClipData();
                if(clip.getItemCount()>10)toast("За один раз можно отправить максимум 10 файлов");
                for(int i=0;i<Math.min(clip.getItemCount(),10);i++)
                    chosen.add(clip.getItemAt(i).getUri());
            }else if(data.getData()!=null)chosen.add(data.getData());
            for(Uri uri:chosen){
                String mime=activity.getContentResolver().getType(uri);
                if(mime==null)mime="application/octet-stream";
                sendUri(target,group,uri,displayName(uri),mime,null);
            }
            if(chosen.size()>0)toast("В очереди на отправку: "+chosen.size()+" файл(ов)");
        }
    }


    /** Small in-chat preview; never use a public or unauthenticated image URL. */
    public void addInlinePreview(LinearLayout parent,JSONObject attachment,boolean mine){
        String kind=attachment.optString("kind","");
        if(!kind.equals("photo") && !kind.equals("video") && !kind.equals("video_note"))return;
        String attachmentId=attachment.optString("id","");
        String url=attachment.optString("url","");
        if(attachmentId.isEmpty() || url.isEmpty())return;
        int imageSize=(int)((kind.equals("video_note")?188:210)*
                activity.getResources().getDisplayMetrics().density);
        LinearLayout align=new LinearLayout(activity);
        align.setGravity(mine?Gravity.RIGHT:Gravity.LEFT);
        parent.addView(align,new LinearLayout.LayoutParams(-1,-2));
        FrameLayout frame=new FrameLayout(activity);
        LinearLayout.LayoutParams layout=new LinearLayout.LayoutParams(imageSize,imageSize);
        layout.setMargins(0,3,0,5);
        align.addView(frame,layout);
        ImageView photo=new ImageView(activity);
        photo.setScaleType(ImageView.ScaleType.CENTER_CROP);
        photo.setBackgroundColor(0xff303942);
        frame.addView(photo,new FrameLayout.LayoutParams(-1,-1));
        if(kind.equals("video_note")){
            photo.setOutlineProvider(new ViewOutlineProvider(){
                @Override public void getOutline(View v,Outline outline){
                    outline.setOval(0,0,v.getWidth(),v.getHeight());
                }
            });
            photo.setClipToOutline(true);
        }else {
            photo.setOutlineProvider(new ViewOutlineProvider(){
                @Override public void getOutline(View v,Outline outline){
                    outline.setRoundRect(0,0,v.getWidth(),v.getHeight(),18*
                        activity.getResources().getDisplayMetrics().density);
                }
            });
            photo.setClipToOutline(true);
        }
        if(!kind.equals("photo")){
            TextView play=new TextView(activity);
            play.setText("▶");play.setTextSize(26);
            play.setTextColor(0xffFFFFFF);play.setGravity(Gravity.CENTER);
            play.setBackgroundColor(0x44000000);
            FrameLayout.LayoutParams overlay=new FrameLayout.LayoutParams(
                    (int)(55*activity.getResources().getDisplayMetrics().density),
                    (int)(55*activity.getResources().getDisplayMetrics().density),Gravity.CENTER);
            frame.addView(play,overlay);
        }
        frame.setOnClickListener(v->openAttachment(attachment));
        Bitmap cached=thumbnails.get(attachmentId);
        if(cached!=null && !cached.isRecycled()){
            photo.setImageBitmap(cached);return;
        }
        api.fetchAttachment(url,(file,error)->{
            if(error!=null || file==null)return;
            new Thread(()->{
                Bitmap bitmap=null;
                try{
                    if(kind.equals("photo")){
                        BitmapFactory.Options opts=new BitmapFactory.Options();
                        opts.inJustDecodeBounds=true;
                        BitmapFactory.decodeFile(file.getAbsolutePath(),opts);
                        opts.inSampleSize=1;
                        while(opts.outWidth/opts.inSampleSize>600 ||
                              opts.outHeight/opts.inSampleSize>600)opts.inSampleSize*=2;
                        opts.inJustDecodeBounds=false;
                        bitmap=BitmapFactory.decodeFile(file.getAbsolutePath(),opts);
                    }else{
                        MediaMetadataRetriever retriever=new MediaMetadataRetriever();
                        try{
                            retriever.setDataSource(file.getAbsolutePath());
                            bitmap=retriever.getFrameAtTime(0,
                                    MediaMetadataRetriever.OPTION_CLOSEST_SYNC);
                            if(bitmap!=null && Math.max(bitmap.getWidth(),bitmap.getHeight())>600){
                                float ratio=600f/Math.max(bitmap.getWidth(),bitmap.getHeight());
                                bitmap=Bitmap.createScaledBitmap(bitmap,
                                        Math.max(1,Math.round(bitmap.getWidth()*ratio)),
                                        Math.max(1,Math.round(bitmap.getHeight()*ratio)),true);
                            }
                        }finally{retriever.release();}
                    }
                }catch(Exception ignored){}
                file.delete();
                Bitmap result=bitmap;
                if(result!=null)activity.runOnUiThread(()->{
                    thumbnails.put(attachmentId,result);
                    // If navigation changed the view is detached; don't change another chat.
                    if(photo.getParent()!=null)photo.setImageBitmap(result);
                });
            },"vainah-thumbnail").start();
        });
    }

    public void openAttachment(JSONObject attachment){
        String path=attachment.optString("url","");
        String mime=attachment.optString("type","application/octet-stream");
        String kind=attachment.optString("kind","file");
        if(!path.startsWith("/api/messenger/v2/file/") &&
                !path.matches("/api/messenger/v2/groups/[a-fA-F0-9-]{36}/file/[a-fA-F0-9-]{36}")){
            toast("Некорректное вложение");return;
        }
        toast("Загрузка медиа…");
        api.fetchAttachment(path,(file,error)->{
            if(error!=null){toast(error);return;}
            if(file==null)return;
            try{
                if(mime.startsWith("image/"))imageDialog(file);
                else if(mime.startsWith("audio/"))audioDialog(file,kind);
                else if(mime.startsWith("video/"))videoDialog(file,kind.equals("video_note"));
                else openExternal(file,mime);
            }catch(Exception ex){file.delete();toast("Не удалось открыть медиа");}
        });
    }

    private void imageDialog(File file){
        BitmapFactory.Options options=new BitmapFactory.Options();
        options.inJustDecodeBounds=true;
        BitmapFactory.decodeFile(file.getAbsolutePath(),options);
        options.inSampleSize=1;
        while(options.outWidth/options.inSampleSize>1600 ||
              options.outHeight/options.inSampleSize>1600)options.inSampleSize*=2;
        options.inJustDecodeBounds=false;
        Bitmap bitmap=BitmapFactory.decodeFile(file.getAbsolutePath(),options);
        if(bitmap==null){file.delete();toast("Повреждённое изображение");return;}
        ImageView view=new ImageView(activity);
        view.setImageBitmap(bitmap);
        view.setScaleType(ImageView.ScaleType.FIT_CENTER);
        int padding=(int)(16*activity.getResources().getDisplayMetrics().density);
        view.setPadding(padding,padding,padding,padding);
        AlertDialog dialog=new AlertDialog.Builder(activity)
                .setTitle("Фотография")
                .setView(view)
                .setPositiveButton("Закрыть",null).create();
        dialog.setOnDismissListener(d->{bitmap.recycle();file.delete();});
        dialog.show();
    }

    private void audioDialog(File file,String kind)throws Exception{
        MediaPlayer player=new MediaPlayer();
        player.setDataSource(file.getAbsolutePath());
        player.prepare();
        LinearLayout panel=new LinearLayout(activity);panel.setOrientation(1);
        int padding=(int)(18*activity.getResources().getDisplayMetrics().density);
        panel.setPadding(padding,padding,padding,padding);
        TextView label=new TextView(activity);
        long durationSeconds=Math.max(0,player.getDuration()/1000);
        String duration=String.format(java.util.Locale.ROOT,"%d:%02d",
                durationSeconds/60,durationSeconds%60);
        label.setText((kind.equals("voice")?"🎤 Голосовое сообщение":"♫ Аудиофайл")
                +"  ·  "+duration);
        label.setTextSize(19);panel.addView(label);
        Button play=new Button(activity);play.setText("▶ Воспроизвести");
        panel.addView(play);
        play.setOnClickListener(v->{
            if(player.isPlaying()){player.pause();play.setText("▶ Продолжить");}
            else {player.start();play.setText("⏸ Пауза");}
        });
        // Telegram-style voice playback speeds, without transcoding the audio file.
        if(android.os.Build.VERSION.SDK_INT>=23){
            Button speed=new Button(activity);
            speed.setText("1× Скорость");
            panel.addView(speed);
            final float[] rates={1.0f,1.5f,2.0f};
            final int[] index={0};
            speed.setOnClickListener(v->{
                index[0]=(index[0]+1)%rates.length;
                float rate=rates[index[0]];
                try{
                    player.setPlaybackParams(player.getPlaybackParams().setSpeed(rate));
                    speed.setText((rate==1.0f?"1×":rate==1.5f?"1.5×":"2×")+" Скорость");
                    if(!player.isPlaying()){player.pause();}
                }catch(IllegalStateException | IllegalArgumentException ex){
                    index[0]=0;
                    speed.setText("1× Скорость");
                    toast("Смена скорости не поддерживается на этом устройстве");
                }
            });
        }
        player.setOnCompletionListener(mp->{play.setText("▶ Повторить");});
        // Release resources if the user leaves the audio dialog; never keep a
        // private media file on disk longer than the active playback session.
        AlertDialog dialog=new AlertDialog.Builder(activity).setTitle("Vainah Audio")
                .setView(panel).setNegativeButton("Закрыть",null).create();
        dialog.setOnDismissListener(d->{player.release();file.delete();});
        dialog.show();
    }

    private void videoDialog(File file,boolean round){
        if(!round){
            VideoView video=new VideoView(activity);
            video.setVideoPath(file.getAbsolutePath());
            video.setMediaController(new MediaController(activity));
            AlertDialog dialog=new AlertDialog.Builder(activity)
                    .setTitle("Видео").setView(video)
                    .setPositiveButton("Закрыть",null).create();
            video.setOnPreparedListener(mp->{mp.setLooping(false);video.start();});
            dialog.setOnDismissListener(d->{video.stopPlayback();file.delete();});
            dialog.show();
            return;
        }
        int width=(int)(280*activity.getResources().getDisplayMetrics().density);
        FrameLayout frame=new FrameLayout(activity);
        TextureView texture=new TextureView(activity);
        FrameLayout.LayoutParams params=new FrameLayout.LayoutParams(width,width,Gravity.CENTER);
        frame.addView(texture,params);
        texture.setOutlineProvider(new ViewOutlineProvider(){
            @Override public void getOutline(View v,Outline outline){
                outline.setOval(0,0,v.getWidth(),v.getHeight());
            }
        });
        texture.setClipToOutline(true);
        MediaPlayer[] player={null};
        AlertDialog dialog=new AlertDialog.Builder(activity).setTitle("Видеокружок")
                .setView(frame).setPositiveButton("Закрыть",null).create();
        texture.setSurfaceTextureListener(new TextureView.SurfaceTextureListener(){
            @Override public void onSurfaceTextureAvailable(SurfaceTexture surface,int w,int h){
                try{
                    MediaPlayer mp=new MediaPlayer();
                    player[0]=mp;
                    mp.setDataSource(file.getAbsolutePath());
                    Surface output=new Surface(surface);
                    mp.setSurface(output);output.release();
                    mp.setLooping(true);
                    mp.setOnPreparedListener(MediaPlayer::start);
                    mp.prepareAsync();
                }catch(Exception e){toast("Видеокружок не воспроизводится");}
            }
            @Override public void onSurfaceTextureSizeChanged(SurfaceTexture surface,int w,int h){}
            @Override public boolean onSurfaceTextureDestroyed(SurfaceTexture surface){
                if(player[0]!=null){player[0].release();player[0]=null;}
                return true;
            }
            @Override public void onSurfaceTextureUpdated(SurfaceTexture surface){}
        });
        dialog.setOnDismissListener(d->{
            if(player[0]!=null){player[0].release();player[0]=null;}
            file.delete();
        });
        dialog.show();
    }

    private void openExternal(File file,String mime){
        try{
            Uri share=FileProvider.getUriForFile(activity,activity.getPackageName()+".media",file);
            Intent open=new Intent(Intent.ACTION_VIEW);
            open.setDataAndType(share,mime);
            open.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            activity.startActivity(Intent.createChooser(open,"Открыть вложение"));
        }catch(ActivityNotFoundException ex){
            file.delete();
            toast("Нет приложения, которое открывает этот формат");
        }
    }

    public void close(){
        cancelRecording();
    }
}
