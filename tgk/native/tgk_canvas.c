/* tgk: bounds-checked pixel primitives for a Termux:GUI RGBA8888 shared buffer.
 * SPDX-License-Identifier: MIT. No Android headers needed; build on Termux/desktop.
 */
#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include <limits.h>

typedef struct { uint8_t *pixels; int width, height, stride; } tgk_surface;

int tgk_surface_init(tgk_surface *s, void *pixels, int w, int h, int stride) {
    if (!s || !pixels || w <= 0 || h <= 0 || w > INT_MAX / 4 ||
        stride < w * 4 || stride <= 0 || (size_t)h > SIZE_MAX/(size_t)stride) return -1;
    s->pixels = (uint8_t *)pixels; s->width = w; s->height = h; s->stride = stride;
    return 0;
}
static inline void put(tgk_surface *s, int x, int y, uint32_t rgba) {
    uint8_t *p = s->pixels + (size_t)y * s->stride + (size_t)x * 4;
    uint32_t a = rgba & 255u;
    if (a == 255) {
        p[0] = (uint8_t)(rgba>>24); p[1] = (uint8_t)(rgba>>16);
        p[2] = (uint8_t)(rgba>>8); p[3] = 255;
    } else if (a) {
        uint32_t inv = 255-a;
        /* straight-alpha source-over, preserving destination alpha */
        uint32_t da=p[3], oa=a+(da*inv+127)/255;
        if (!oa) return;
        uint32_t src[3] = {(rgba>>24)&255,(rgba>>16)&255,(rgba>>8)&255};
        for (int k=0;k<3;k++) {
            uint32_t pm = src[k]*a + (p[k]*da*inv+127)/255;
            p[k]=(uint8_t)((pm+oa/2)/oa);
        }
        p[3]=(uint8_t)oa;
    }
}
void tgk_clear(tgk_surface *s, uint32_t rgba) {
    if (!s || !s->pixels) return;
    uint8_t r=rgba>>24, g=rgba>>16, b=rgba>>8, a=rgba;
    for (int y=0;y<s->height;y++) {
        uint8_t *row=s->pixels+(size_t)y*s->stride;
        for (int x=0;x<s->width;x++) { uint8_t *p=row+4*x; p[0]=r;p[1]=g;p[2]=b;p[3]=a; }
    }
}
void tgk_rect(tgk_surface *s, int x,int y,int w,int h,uint32_t rgba) {
    if(!s||!s->pixels||w<=0||h<=0) return;
    int64_t xx=(int64_t)x+w, yy=(int64_t)y+h;
    int x0=x<0?0:x, y0=y<0?0:y;
    int x1=xx>s->width?s->width:(int)xx, y1=yy>s->height?s->height:(int)yy;
    for(int j=y0;j<y1;j++) for(int i=x0;i<x1;i++) put(s,i,j,rgba);
}
void tgk_circle(tgk_surface *s,int cx,int cy,int rad,uint32_t rgba) {
    if(!s||!s->pixels||rad<0)return;
    int64_t x0=(int64_t)cx-rad, x1=(int64_t)cx+rad;
    int64_t y0=(int64_t)cy-rad, y1=(int64_t)cy+rad;
    if(x0<0)x0=0;
    if(y0<0)y0=0;
    if(x1>=s->width)x1=s->width-1;
    if(y1>=s->height)y1=s->height-1;
    int64_t rr=(int64_t)rad*rad;
    for(int64_t y=y0;y<=y1;y++)for(int64_t x=x0;x<=x1;x++) {
        int64_t dx=x-cx,dy=y-cy;
        if(dx*dx+dy*dy<=rr)put(s,(int)x,(int)y,rgba);
    }
}
static int absdiff(int a,int b){return a>b?a-b:b-a;}
void tgk_line(tgk_surface *s,int x0,int y0,int x1,int y1,uint32_t rgba) {
    if(!s||!s->pixels)return;
    /* clip in double precision before stepping to avoid huge offscreen loops */
    double ax=x0,ay=y0,bx=x1,by=y1,dx=bx-ax,dy=by-ay;
    double low=0.0,high=1.0;
    double p[4]={-dx,dx,-dy,dy};
    double q[4]={ax, (double)s->width-1-ax,ay,(double)s->height-1-ay};
    for(int i=0;i<4;i++) {
        if(p[i]==0) {if(q[i]<0)return;continue;}
        double t=q[i]/p[i];
        if(p[i]<0) {if(t>low)low=t;}else {if(t<high)high=t;}
    }
    if(low>high)return;
    int a=(int)lround(ax+low*dx),b=(int)lround(ay+low*dy);
    int c=(int)lround(ax+high*dx),d=(int)lround(ay+high*dy);
    int sx=a<c?1:-1,sy=b<d?1:-1, adx=absdiff(a,c),ady=absdiff(b,d);
    int err=adx-ady;
    for (;;) {
        if(a>=0&&a<s->width&&b>=0&&b<s->height)put(s,a,b,rgba);
        if(a==c&&b==d)break;
        int e=2*err;
        if(e>-ady){err-=ady;a+=sx;}
        if(e<adx){err+=adx;b+=sy;}
    }
}

void tgk_gradient(tgk_surface *s, uint32_t top, uint32_t bottom) {
    if (!s||!s->pixels)return;
    uint8_t a[4]={(uint8_t)(top>>24),(uint8_t)(top>>16),(uint8_t)(top>>8),(uint8_t)top};
    uint8_t b[4]={(uint8_t)(bottom>>24),(uint8_t)(bottom>>16),(uint8_t)(bottom>>8),(uint8_t)bottom};
    for (int y=0;y<s->height;y++) {
        int denom=s->height>1?s->height-1:1;
        uint8_t c[4];
        for(int k=0;k<4;k++) c[k]=(uint8_t)(((int)a[k]*(denom-y)+(int)b[k]*y+denom/2)/denom);
        uint8_t *p=s->pixels+(size_t)y*s->stride;
        for(int x=0;x<s->width;x++){for(int k=0;k<4;k++)p[4*x+k]=c[k];}
    }
}
/* Maps touch coordinates into buffer coordinates (resizeMode 0=stretch, 1=fit-center).
   fit-center returns -1 when touching letterboxed area. */
int tgk_map_touch(int view_w,int view_h,int canvas_w,int canvas_h,int mode,
                   double x,double y,int *out_x,int *out_y) {
    if(!out_x||!out_y||view_w<=0||view_h<=0||canvas_w<=0||canvas_h<=0||
       !isfinite(x)||!isfinite(y))return -1;
    if(mode==1) {
        double sx=(double)view_w/canvas_w,sy=(double)view_h/canvas_h;
        double scale=sx<sy?sx:sy;
        x=(x-(view_w-canvas_w*scale)*.5)/scale;
        y=(y-(view_h-canvas_h*scale)*.5)/scale;
    } else {
        x=x*canvas_w/view_w;y=y*canvas_h/view_h;
    }
    if(x<0||y<0||x>=canvas_w||y>=canvas_h)return -1;
    *out_x=(int)x;*out_y=(int)y;return 0;
}
