import os
import ftplib

def upload_image_to_ftp(image_path):
    ftp_server = 'ftp.runright.io'
    ftp_user = 'runright'
    ftp_password = 'Nt3-t774*tmQQX'
    ftp_path = '/public_html/wp-content/uploads/cer/images/company' 
    use_tls = True 
    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"The file at {image_path} does not exist.")
        
        if not os.path.isfile(image_path):
            raise ValueError(f"The path {image_path} is not a file.")

        if use_tls:
            ftp = ftplib.FTP_TLS(ftp_server)
        else:
            ftp = ftplib.FTP(ftp_server)

        ftp.login(user=ftp_user, passwd=ftp_password)
        
        if use_tls:
            ftp.prot_p() 

        # Include the filename in the ftp_path and ensure forward slashes
        filename = os.path.basename(image_path)
        remote_path = os.path.join(ftp_path, filename).replace('\\', '/')

        with open(image_path, 'rb') as file:
            ftp.storbinary(f'STOR {remote_path}', file)

        ftp.quit()
        print(f"Successfully uploaded {image_path} to {ftp_server}/{remote_path}")

    except FileNotFoundError as fnf_error:
        print(fnf_error)
    except ValueError as ve:
        print(ve)
    except ftplib.all_errors as e:
        print(f"FTP error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

