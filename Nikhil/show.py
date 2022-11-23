import cv2

while True:
    im = cv2.imread("/home/ultratech-01/Downloads/Nikhil/TMP/_tmp.jpg")
    im = cv2.resize(im, (int(im.shape[1]*0.4),int(im.shape[0]*0.4)))
    cv2.imshow("iamge", im)    
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cv2.destroyAllWindows()